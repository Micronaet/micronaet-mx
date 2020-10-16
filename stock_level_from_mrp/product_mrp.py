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

_logger = logging.getLogger(__name__)


class MrpProductionWorkcenterLine(osv.osv):
    """ Model name: Lavoration
    """

    _inherit = 'mrp.production.workcenter.line'

    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Update product level from production
        """
        product_pool = self.pool.get('product.product')
        company_pool = self.pool.get('res.company')

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

        lavoration_ids = self.search(cr, uid, [
            ('real_date_planned', '>=', from_text),
            ('real_date_planned', '<', now_text),
            ], context=context)
        _logger.warning('Lavoration found: %s Period: [>=%s <%s]' % (
            len(lavoration_ids),
            from_text,
            now_text,
            ))

        product_medium = {}
        for lavoration in self.browse(
                cr, uid, lavoration_ids, context=context):
            for material in lavoration.bom_material_ids:
                product = material.product_id
                quantity = material.quantity
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity

        _logger.warning('Product found: %s' % len(product_medium))
        for product in product_medium:
            total = product_medium[product]
            if product.manual_stock_level:
                continue

            if not total:
                medium_stock_qty = 0.0
            else:
                medium_stock_qty = total / stock_level_days

            product_pool.write(cr, uid, [product.id], {
                'medium_stock_qty': medium_stock_qty,
                'min_stock_level':
                    product.day_min_level * medium_stock_qty,
                    # product_pool.round_interger_order(
                    #    product.day_min_level * medium_stock_qty,
                    #    approx=product.approx_integer,
                    #    mode=product.approx_mode),
                'max_stock_level':
                    product.day_max_level * medium_stock_qty,
                    # product_pool.round_interger_order(
                    #    product.day_max_level * medium_stock_qty,
                    #    approx=product.approx_integer,
                    #    mode=product.approx_mode),
                'ready_stock_level':
                    product.day_max_ready_level * medium_stock_qty,
                    # product_pool.round_interger_order(
                    #    product.day_max_ready_level * medium_stock_qty,
                    #    approx=product.approx_integer,
                    #    mode=product.approx_mode),
                }, context=context)
        return True


class ResCompany(osv.osv):
    """ Model name: Parameters
    """

    _inherit = 'res.company'

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
            'Codice', 'Descrizione', 'UM',
            'Appr.', 'Mod.',
            'Min Mexal', 'Max Mexal',

            'Manuale', 'Lead time', 'M(x)',

            'Liv. min. gg.', 'Liv. min.',
            'Liv. max. gg.', 'Liv. max.',
            'Liv. pronto gg.', 'Liv. pronto',
            ]

        width = [
            15, 25, 5,
            6, 6,
            12, 12,
            5, 12, 12,
            12, 12,
            12, 12,
            12, 12,
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
                #('min_stock_level', '>', 0),
                ]),
            ('Non presenti', [
                ('min_stock_level', '<=', 0),
                ]),
            )
        # Create all pages:
        excel_format = {}
        for ws_name, product_filter in ws_list:
            excel_pool.create_worksheet(name=ws_name)

            excel_pool.column_width(ws_name, width)
            # excel_pool.row_height(ws_name, row_list, height=10)

            # -----------------------------------------------------------------
            # Generate format used (first time only):
            # -----------------------------------------------------------------
            if not excel_format:
                excel_pool.set_format()
                excel_format['title'] = excel_pool.get_format(key='title')
                excel_format['header'] = excel_pool.get_format(key='header')
                excel_format['text'] = excel_pool.get_format(key='text')
                excel_format['number'] = excel_pool.get_format(key='number')

            # -----------------------------------------------------------------
            # Write title / header
            # -----------------------------------------------------------------
            row = 0
            excel_pool.write_xls_line(
                ws_name, row, [ws_name], default_format=excel_format['title'])

            row += 1
            excel_pool.write_xls_line(
                ws_name, row, header, default_format=excel_format['header'])

            # -----------------------------------------------------------------
            # Product selection:
            # -----------------------------------------------------------------
            product_ids = product_pool.search(
                cr, uid, product_filter, context=context)

            product = product_pool.browse(cr, uid, product_ids,
                context=context)

            row += 1
            for product in sorted(product, key=lambda x: x.default_code):
                line = [
                    product.default_code or '',
                    product.name or '',
                    product.uom_id.name or '',

                    product.approx_integer,
                    product.approx_mode,

                    product.minimum_qty,
                    product.maximum_qty,

                    product.manual_stock_level,
                    product.day_leadtime,
                    product.medium_stock_qty,

                    product.day_min_level,
                    product.min_stock_level,

                    product.day_max_level,
                    product.max_stock_level,

                    product.day_max_ready_level,
                    product.ready_stock_level,
                    ]

                excel_pool.write_xls_line(
                    ws_name, row, line, default_format=excel_format['text'])
                row += 1
        return excel_pool.return_attachment(
            cr, uid, 'Livelli prodotto', 'livelli_magazzino.xlsx',
            version='7.0', php=True, context=context)

    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Button from company
        """
        return self.pool.get('mrp.production.workcenter.line'
            ).update_product_level_from_production(
                cr, uid, ids, context=context)
    _columns = {
        'stock_level_days': fields.integer(
            'Stock level days', help='Days for from data till today'),

        # Manage mode?
        'stock_level_mode': fields.selection([
            ('medium', 'Medium'),
            # ('variant', 'Medium + variant'),
            # ('period', 'Month period'),
            ], 'Stock level mode', required=True),
        }

    _defaults = {
        'stock_level_days': lambda *x: 180,
        'stock_level_mode': lambda *x: 'medium',
        }


class ProductProduct(osv.osv):
    """ Model name: ProductProduct
    """

    _inherit = 'product.product'
