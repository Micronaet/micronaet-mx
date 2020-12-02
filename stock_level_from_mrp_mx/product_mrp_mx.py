#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
import xlsxwriter
from openerp.osv import fields, osv, expression
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)
import pdb

_logger = logging.getLogger(__name__)


class ResCompany(osv.osv):
    """ Model name: Parameters
    """

    _inherit = 'res.company'

    _columns = {
    }

    def get_type(self, code, uom):
        """ Extract type from code
        """
        code = (code or '').strip().upper()
        uom = (uom or '').upper()

        if not code:
            return _('Not assigned')

        start = code[0]
        end = code[-1]

        if uom == 'PCE':  # Machinery and Component
            return 'COMP'
        if start in 'PR':  # Waste
            return 'REC'
        if start in 'AB':  # Raw materials
            return 'MP'
        if end == 'X':  # Production (MX)
            return 'PT'
        return 'IT'  # Re-sold (IT)

    # Override for MX report (was different)
    def extract_product_level_xlsx(self, cr, uid, ids, context=None):
        """ Extract current report stock level
        """
        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        product_pool = self.pool.get('product.product')

        # ---------------------------------------------------------------------
        #                          Excel export:
        # ---------------------------------------------------------------------
        # Setup:
        header = [
            u'Tipo',

            u'Codigo', u'Descripcion', u'UM',
            u'Appr.', u'Mod.',

            u'Manual', u'Tiempo de Entrega', u'Promedio Kg/Dia',

            u'Nivel Minimo Dias', u'Nivel Minimo Kg.',
            u'Nivel Maximo Dia', u'Nivel Maximo Kg.',
            u'Contipaq', u'Status', u'Obsolete',
            ]

        width = [
            18,
            15, 25, 5,
            6, 9,
            5, 8, 8,
            8, 8,
            8, 8,
            10, 10, 5,
            ]

        # ---------------------------------------------------------------------
        # Create WS:
        # ---------------------------------------------------------------------
        ws_list = (
            ('Livelli auto', [
                ('manual_stock_level', '=', False),
                ('medium_stock_qty', '>', 0),
                ]),
            ('Livelli manuali', [
                ('manual_stock_level', '=', True),
                # ('min_stock_level', '>', 0),
                ]),
            ('Non presenti', [  # Not change the ws_name
                ('min_stock_level', '<=', 0),
                ]),
            )
        # Create all pages:
        excel_format = {}
        removed_ids = []
        for ws_name, product_filter in ws_list:
            excel_pool.create_worksheet(name=ws_name)

            excel_pool.column_width(ws_name, width)
            # excel_pool.row_height(ws_name, row_list, height=10)
            excel_pool.freeze_panes(ws_name, 1, 2)
            excel_pool.column_hidden(ws_name, [4, 5, 7])

            # -----------------------------------------------------------------
            # Generate format used (first time only):
            # -----------------------------------------------------------------
            if not excel_format:
                excel_pool.set_format()
                excel_format['title'] = excel_pool.get_format(key='title')
                excel_format['header'] = excel_pool.get_format(key='header')
                excel_format['header_wrap'] = excel_pool.get_format(
                    key='header_wrap')
                excel_format['text'] = excel_pool.get_format(key='text')
                excel_format['right'] = excel_pool.get_format(key='text_right')
                excel_format['number'] = excel_pool.get_format(key='number')

            # -----------------------------------------------------------------
            # Write title / header
            # -----------------------------------------------------------------
            row = 0
            excel_pool.write_xls_line(
                ws_name, row, header,
                default_format=excel_format['header_wrap'])
            excel_pool.autofilter(ws_name, row, row, 0, len(header) - 1)
            excel_pool.row_height(ws_name, [row], height=38)

            # -----------------------------------------------------------------
            # Product selection:
            # -----------------------------------------------------------------
            product_ids = product_pool.search(
                cr, uid, product_filter, context=context)

            if ws_name == 'Non presenti' and removed_ids:
                # Add also removed from other loop
                product_ids = list(set(product_ids).union(set(removed_ids)))

            products = product_pool.browse(
                cr, uid, product_ids,
                context=context)

            # TODO add also package data!!!
            row += 1
            for product in sorted(products, key=lambda x: (
                    self.get_type(x.default_code, x.uom_id.name),
                    x.default_code)):
                # Filter code:
                default_code = product.default_code
                if not default_code:
                    _logger.error('Product %s has no code' % product.name)
                    continue
                product_type = self.get_type(
                    product.default_code, product.uom_id.name)

                # Remove REC and SER product (go in last page):
                if ws_name != 'Non presenti' and product_type == 'REC' or \
                        default_code.startswith('SER'):
                    removed_ids.append(product.id)
                    continue

                account_qty = int(product.accounting_qty)
                min_stock_level = int(product.min_stock_level)
                if account_qty < min_stock_level:
                    state = _('Under level')
                elif account_qty < 0:
                    state = _('Negative')
                else:
                    state = _('OK')

                line = [
                    product_type,
                    default_code or '',
                    product.name or '',
                    product.uom_id.name or '',

                    (product.approx_integer, excel_format['right']),
                    product.approx_mode or '',

                    (product.manual_stock_level or '', excel_format['right']),
                    product.day_leadtime or '',
                    (product.medium_stock_qty, excel_format['number']),

                    (product.day_min_level, excel_format['right']),
                    (int(min_stock_level), excel_format['right']),

                    (product.day_max_level, excel_format['right']),
                    (int(product.max_stock_level), excel_format['right']),

                    (account_qty, excel_format['right']),
                    state,
                    'X' if product.stock_obsolete else '',
                    ]

                excel_pool.write_xls_line(
                    ws_name, row, line, default_format=excel_format['text'])
                row += 1
        return excel_pool.return_attachment(
            cr, uid, 'Livelli prodotto MX', 'stock_level_MX.xlsx',
            version='7.0', php=True, context=context)


class MrpProductionWorkcenterLineOverride(osv.osv):
    """ Model name: Override for add product in calc of medium
    """

    _inherit = 'mrp.production.workcenter.line'

    # Override to medium also product and packages:
    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Update product level from production (this time also product)
        """
        _logger.info('Updating medium from MRP (final product)')
        company_pool = self.pool.get('res.company')
        load_pool = self.pool.get('mrp.production.workcenter.load')

        # Get parameters:
        company_ids = company_pool.search(cr, uid, [], context=context)
        company = company_pool.browse(
            cr, uid, company_ids, context=context)[0]
        stock_level_days = company.stock_level_days
        if not stock_level_days:
            raise osv.except_osv(
                _('Error stock management'),
                _('Setup the parameter in company form'),
                )

        now = datetime.now()
        from_date = now - timedelta(days=stock_level_days)
        now_text = '%s 00:00:00' % now.strftime(
             DEFAULT_SERVER_DATE_FORMAT)
        from_text = '%s 00:00:00' % from_date.strftime(
             DEFAULT_SERVER_DATE_FORMAT)

        load_ids = load_pool.search(cr, uid, [
            ('date', '>=', from_text),
            ('date', '<', now_text),
            ('recycle', '=', False),
            ], context=context)
        _logger.warning('Load found: %s Period: [>=%s <%s]' % (
            len(load_ids),
            from_text,
            now_text,
            ))

        product_medium = {}
        for load in load_pool.browse(
                cr, uid, load_ids, context=context):

            # -----------------------------------------------------------------
            # Product:
            # -----------------------------------------------------------------
            product = load.product_id  # production_id.product_id
            quantity = load.product_qty
            if product in product_medium:
                product_medium[product] += quantity
            else:
                product_medium[product] = quantity

            # -----------------------------------------------------------------
            # Recycle:
            # -----------------------------------------------------------------
            # recycle_product_id  # TODO not used

            # -----------------------------------------------------------------
            # Package:
            # -----------------------------------------------------------------
            product = load.package_id.linked_product_id
            quantity = load.ul_qty
            if product and quantity:
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity

            # -----------------------------------------------------------------
            # Package:
            # -----------------------------------------------------------------
            product = load.pallet_product_id
            quantity = load.pallet_qty
            if product and quantity:
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity

        # Update medium in product:
        self.update_product_medium_from_dict(
            cr, uid, product_medium, stock_level_days, context=context)

        # Call original method for raw materials:
        return super(MrpProductionWorkcenterLineOverride, self).\
            update_product_level_from_production(cr, uid, ids, context=context)
