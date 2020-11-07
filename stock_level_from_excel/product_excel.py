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
import logging
from openerp.osv import fields, osv, expression
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)
import xlrd
import pdb

_logger = logging.getLogger(__name__)


class MrpProductionWorkcenterLine(osv.osv):
    """ Model name: Lavoration
    """

    _inherit = 'mrp.production.workcenter.line'

    # Override so update after update MRP:
    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Update product level from production
        """
        _logger.info('Update marketed product medium')
        product_pool = self.pool.get('product.product')
        company_pool = self.pool.get('res.company')

        # ---------------------------------------------------------------------
        # A. Update marketed product:
        # ---------------------------------------------------------------------
        # Fixed parameters:
        columns_position = {
            'date': 1,
            # 'invoice': 7,
            'default_code': 20,
            # 'name': 21,
            'qty': 22,
            # 'uom': 23,
            # 'price': 24,
        }
        start_test = 'INVOICE DATE'

        # Dynamic parameters:
        company_ids = company_pool.search(cr, uid, [], context=context)
        company = company_pool.browse(
            cr, uid, company_ids, context=context)[0]

        pdb.set_trace()
        stock_level_external_excel = os.path.expanduser(
            company.stock_level_external_excel or '~/VTA PCA 2011A.xlsx')
        stock_level_days = company.stock_level_days
        if not stock_level_external_excel:
            raise osv.except_osv(
                _('Error stock management'),
                _('Setup the parameter in company form (input file)'),
                )

        now = datetime.now()
        from_date = now - timedelta(days=stock_level_days)
        now_text = '%s 00:00:00' % now.strftime(
             DEFAULT_SERVER_DATE_FORMAT)
        from_text = '%s 00:00:00' % from_date.strftime(
             DEFAULT_SERVER_DATE_FORMAT)

        # A1. Search product marketed:
        product_ids = self.search(cr, uid, [
            ('default_code', '=ilike', 'R%'),
            ('default_code', '=ilike', 'S%'),
            ('default_code', 'not =ilike', '%X'),
            ], context=context)

        _logger.warning('Imported product #%s [%s - %s]' % (
            len(product_ids),
            from_text,
            now_text,
            ))

        # A2. Prepare dict for medium
        product_medium = {}
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            default_code = product.default_code
            product_medium[default_code] = 0.0

        # A3. Load data from Excel:
        try:
            wb = xlrd.open_workbook(stock_level_external_excel)
        except:
            _logger.error(
                '[ERROR] Cannot read XLS file: %s' % stock_level_external_excel
            )
            return False

        ws = wb.sheet_by_index(0)
        _logger.info('Read XLS file: %s' % stock_level_external_excel)
        start = False
        for row in range(ws.nrows):
            date = ws.cell(row, columns_position['date']).value
            if not start and date == start_test:
                start = True
                continue

            default_code = ws.cell(row, columns_position['default_code']).value
            if not(start and date and default_code in product_medium):
                continue

            # Load data for medium
            qty = ws.cell(row, columns_position['qty']).value
            product_medium[default_code] += qty

        # A4. Update product medium
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
                'max_stock_level':
                    product.day_max_level * medium_stock_qty,
                'ready_stock_level':
                    product.day_max_ready_level * medium_stock_qty,
                }, context=context)

        # ---------------------------------------------------------------------
        # B. Update original procedure from MRP:
        # ---------------------------------------------------------------------
        return super(MrpProductionWorkcenterLine, self).\
            update_product_level_from_production(cr, uid, ids, context=context)


class ResCompany(osv.osv):
    """ Model name: Parameters
    """

    _inherit = 'res.company'

    _columns = {
        'stock_level_external_excel': fields.char(
            'Stock movement file', size=100,
            help='Path for external XLSX file for stock movement',
        )
    }
