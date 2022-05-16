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
try:
    import xlrd  # problem in pan!
except:
    pass
import pdb

_logger = logging.getLogger(__name__)


class MrpProductionWorkcenterLine(osv.osv):
    """ Model name: Job
    """

    _inherit = 'mrp.production.workcenter.line'

    def get_file(self, url, fullname):
        """ Extract from Dropbox
        """
        import requests
        _logger.info('Downloading file %s from Dropbox' % fullname)
        reply = requests.get(url)
        attachment_data = reply.content
        with open(fullname, 'wb') as f:
            f.write(attachment_data)

    # Override so update after update MRP:
    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Update product level from production
        """
        def get_excel_date(value, wb):
            """ Extract ISO date
            """
            months = {
                'GEN': '01',
                'FEB': '02',
                'MAR': '03',
                'APR': '04',
                'MAG': '05',
                'GIU': '06',
                'LUG': '07',
                'AGO': '08',
                'SET': '09',
                'OCT': '10',
                'NOV': '11',
                'DEC': '12',

                'DIC': '12',
            }
            if not value:
                return ''

            # Preformat for Excel date:
            if type(value) in (float, int):
                value = str(xlrd.xldate.xldate_as_datetime(
                    value, wb.datemode))[:10]
                return value

            res = ''
            value = value.strip()
            value_item = value.split('/')
            if len(value_item) == 3:
                if len(value_item[2]) == 4:
                    pass  # correct
                elif len(value_item[2]) == 2:
                    value_item[2] = '20%s' % value_item[2]
                elif value_item == '209':
                    value_item[2] = '2019'
                else:
                    _logger.error('Unmanaged error:')

                if value_item[1].upper() in months:
                    value_item[1] = months[value_item[1].upper()]

                res = '%s-%02d-%02d' % (
                    value_item[2],
                    int(value_item[1]),
                    int(value_item[0]),
                )
            else:
                res = value  # Nothing
            # _logger.warning(' ' * 70 + '>>>>>> From %s to %s' % (value, res))
            return res

        _logger.info('Update marketed product medium (from Excel)')
        product_pool = self.pool.get('product.product')
        company_pool = self.pool.get('res.company')

        # ---------------------------------------------------------------------
        # A. Update marketed product:
        # ---------------------------------------------------------------------
        # Fixed parameters:
        columns_position = {
            'date': 1,
            # 'invoice': 7,
            'default_code': 25,
            # 'name': 21,
            'qty': 27,
            # 'uom': 23,
            # 'price': 24,
        }
        start_test = 'INVOICE DATE'
        sheet_name = 'BASE'

        # Dynamic parameters:
        company_ids = company_pool.search(cr, uid, [], context=context)
        company = company_pool.browse(
           cr, uid, company_ids, context=context)[0]
        stock_level_days = company.stock_level_mm_days
        # TODO use it:
        stock_level_obsolete_days = company.stock_level_obsolete_days

        # Generate file:
        dropbox_link = context.get('dropbox_link')
        if not dropbox_link:
            _logger.error(
                'Setup the scheduled command with dropbox_link parameter')
        now = datetime.now()
        now_text = str(now)[:19].replace(
            '/', '_').replace(':', '_').replace('-', '_')
        temp_filename = '/tmp/account_status_%s.xlsx' % now_text
        self.get_file(dropbox_link, temp_filename)
        if not temp_filename:
            raise osv.except_osv(
                _('Error stock management'),
                _('Setup the parameter in company form (input file)'),
                )

        from_date = now - timedelta(days=stock_level_days)
        from_obsolete_date = now - timedelta(days=stock_level_days)
        now_text = '%s 00:00:00' % now.strftime(
             DEFAULT_SERVER_DATE_FORMAT)
        from_text = '%s 00:00:00' % from_date.strftime(
             DEFAULT_SERVER_DATE_FORMAT)
        from_obsolete_text = '%s 00:00:00' % from_obsolete_date.strftime(
             DEFAULT_SERVER_DATE_FORMAT)

        # A1. Search product marketed:
        log_f = open('/tmp/odoo_select.log', 'w')
        cr.execute('''
            SELECT id from product_product 
            WHERE default_code is not null AND
                  SUBSTRING (default_code, 1, 1) IN (
                      'D', 'E', 'F', 'G', 'H', 'L', 'M', 
                      'O', 'P', 'R', 'S', 'X') AND 
                  SUBSTRING (default_code, 1, 3) NOT IN ('OLD', 'SER');
        ''')
        product_ids = [record[0] for record in cr.fetchall()]

        log_f.write('Selezionati prodotti iniziano per '
                    'D, E, F, G, H, L, M, O, P, R, S, X\n'
                    'Rimosso quelli che iniziano per OLD e SER\n\n')
        _logger.warning('Imported product #%s [%s - %s]' % (
            len(product_ids),
            from_text,
            now_text,
            ))

        # A2. Prepare dict for medium
        product_medium = {}
        product_obsolete = {}
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):

            default_code = product.default_code
            if not default_code:
                log_f.write('%s|Codice prodotto non trovato\n' % default_code)
                _logger.error('Product %s has no code' % product.name)
                continue

            if default_code not in product_obsolete:
                product_obsolete[default_code] = True

            if default_code.endswith('X'):
                log_f.write(
                    '%s|Prodotto saltato finisce per X\n' % default_code)
                continue
            if default_code in product_medium:
                log_f.write('%s|Prodotto doppio\n' % default_code)
                _logger.error('Product double: %s' % default_code)
            else:
                log_f.write('%s|Prodotto inserito\n' % default_code)
                product_medium[default_code] = [0.0, product]
        log_f.close()

        # A3. Load data from Excel:
        try:
            wb = xlrd.open_workbook(temp_filename)
        except:
            _logger.error(
                '[ERROR] Cannot read XLS file: %s' % temp_filename
            )
            return False

        # A3. Load data from Excel:
        log_f = open('/tmp/excel_data.log', 'w')
        ws = wb.sheet_by_name(sheet_name)
        _logger.info('Read XLS file: %s' % temp_filename)
        start = False
        for row in range(ws.nrows):
            date = get_excel_date(
                ws.cell(row, columns_position['date']).value, wb)
            if not start and date == start_test:
                _logger.info('%s. Line not used: Start line' % (row + 1))
                start = True
                continue

            if date < from_text or date > now_text:  # Out of period range:
                _logger.info('%s. Line not used out of range %s' % (
                    row + 1, date))
                continue

            default_code = ws.cell(row, columns_position['default_code']).value
            if not(start and date and default_code in product_medium):
                log_f.write('%s|%s|%s||Prod. non in lista\n' % (
                    row+1, date, default_code))

                _logger.info(
                    '%s. Line not used (no start or no product watched: %s' % (
                        row + 1,
                        default_code,
                    ))
                continue

            # Load data for medium
            qty = ws.cell(row, columns_position['qty']).value
            if type(qty) not in (float, int):
                log_f.write('%s|%s|%s|%s|Q. non usata\n' % (
                    row+1, date, default_code, qty))
                _logger.error(
                    '%s. Line not used (qty not float: %s' % (
                        row + 1,
                        qty,
                    ))
                continue

            if date > from_obsolete_text:  # Not obsolete:
                product_obsolete[default_code] = False

            product_medium[default_code][0] += qty
            _logger.info('%s. Line used %s - %s' % (
                row + 1,
                default_code,
                qty,
            ))
            log_f.write('%s|%s|%s|%s|Usato %s\n' % (
                row + 1, date, default_code, qty,
                '(obsoleto)' if product_obsolete[default_code] else ''))
        log_f.close()

        # A4. Update product medium
        _logger.warning('Product found: %s' % len(product_medium))

        log_f = open('/tmp/excel_medium.log', 'w')
        log_f.write('Codice|Totale|Giorni|Media|Mix|Max|Ready\n')
        for key in product_medium:
            total, product = product_medium[key]
            default_code = product.default_code
            if product.manual_stock_level:
                continue

            if not total:
                medium_stock_qty = 0.0
                _logger.info(
                    'Update product without level: %s' % default_code)
            else:
                medium_stock_qty = total / stock_level_days
                _logger.info(
                    'Update product with level: %s' % default_code)

            min_stock_level = product.day_min_level * medium_stock_qty
            max_stock_level = product.day_max_level * medium_stock_qty
            ready_stock_level = product.day_max_ready_level * medium_stock_qty

            # Log message:
            log_f.write('%s|%s|%s|%s|%s|%s|%s\n' % (
                default_code, total, stock_level_days, medium_stock_qty,
                min_stock_level, max_stock_level, ready_stock_level
            ))

            """
            if default_code[0] in 'RP':
                day_min_level = 30
                day_max_level = 37
            else:
                day_min_level = 60
                day_max_level = 67
                """

            product_pool.write(cr, uid, [product.id], {
                'medium_origin': 'accounting',
                'medium_stock_qty': medium_stock_qty,
                'stock_obsolete':  product_obsolete[default_code],

                # TODO Force different values?
                # 'day_min_level': day_min_level,
                # 'day_max_level': day_max_level,
                'product_imported': True,

                'min_stock_level': min_stock_level,
                'max_stock_level': max_stock_level,
                'ready_stock_level': ready_stock_level,
                }, context=context)

        _logger.info('Update marketed product: %s' % len(product_medium))
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
        ),

        # Days management for stats:
        'stock_level_mm_days': fields.integer(
            'Stock level MM days', required=True,
            help='Days for from data till today (period for stock movement'),
        'stock_level_obsolete_days': fields.integer(
            'Stock level obsolete days', required=True,
            help='Days for from data till today (> consider product obsolete'),
    }

    _defaults = {
        'stock_level_mm_days': lambda *x: 180,
        'stock_level_obsolete_days': lambda *x: 90,
    }


class ProductProduct(osv.osv):
    """ Model name: Parameters
    """

    _inherit = 'product.product'

    _columns = {
        'product_imported': fields.char('Imported product'),
    }
