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
import xlsxwriter
from openerp.osv import fields, osv, expression
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)
import pdb

_logger = logging.getLogger(__name__)


class ContipaqStockMove(osv.osv):
    """ Model name: Contipaq Stock move
    """

    _name = 'contipaq.stock.move'
    _rec_name = 'name'
    _order = 'date'

    _columns = {
        'name': fields.char('Rif. ordine', size=20),
        'type': fields.char('Tipo di ordine', size=5),
        'date': fields.datetime('Data ordine'),
        'deadline': fields.datetime('Scadenza ordine'),
        'partner_name': fields.char('Nome partner', size=50),

        'default_code': fields.char('Codice prodotto', size=20),
        'quantity': fields.float('Q.', digits=(10, 5)),
        'uom': fields.char('UM', size=5),  # T, K, P, (N)
    }


class ResCompany(osv.osv):
    """ Model name: Parameters
    """

    _inherit = 'res.company'

    _columns = {
    }

    def get_type(self, product):  # code, uom):
        """ Extract type from code
        """
        if product.not_in_status:
            return 'EXCL'

        code = product.default_code or ''
        uom = product.uom_id.name or ''

        code = code.strip().upper()
        uom = uom.upper()

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
        """ Extract current report stock level MX Version
        """
        if context is None:
            context = {}
        save_mode = context.get('save_mode')

        # Pool used:
        excel_pool = self.pool.get('excel.writer')
        product_pool = self.pool.get('product.product')
        move_pool = self.pool.get('contipaq.stock.move')

        # ---------------------------------------------------------------------
        # Log system:
        # ---------------------------------------------------------------------
        log_file = {
            'contipaq': open('/tmp/ROP_contipaq.csv', 'w'),
            'used': open('/tmp/ROP_used.csv', 'w'),
            'not_used': open('/tmp/ROP_not_used.csv', 'w'),
            'pre_not_used': open('/tmp/ROP_pre_not_used.csv', 'w'),
        }

        def save_log(mode, message):
            """ Save log data on file:
            """
            message = '%s\n' % message
            try:
                log_file[mode].write(message)
            except:
                _logger.error('Error writing log: %s' % message)

        # ---------------------------------------------------------------------
        # Collect order data (Contipaq mode):
        # ---------------------------------------------------------------------
        now = str(datetime.now())[:10]
        move_ids = move_pool.search(cr, uid, [
            ('type', '!=', 'PO'),  # Comes from purchase order
            ], context=context)
        move_db = {}
        for move in move_pool.browse(cr, uid, move_ids, context=context):
            default_code = move.default_code
            if not default_code:
                continue
            uom = move.uom
            quantity = move.quantity
            deadline = move.deadline
            if uom == 'T':
                quantity *= 1000.0
                uom = 'K'

            if default_code not in move_db:
                new = 'NUOVO'
                move_db[default_code] = {
                    'total': 0.0,
                    'comment': '',
                    'deadlined': False,
                }
            else:
                new = 'VECCHIO'

            # -----------------------------------------------------------------
            # Logging mode:
            # -----------------------------------------------------------------
            save_log(
                'contipaq',
                '%s|%s|%s|%s|%s' % (
                    default_code, uom, quantity, deadline, new),
            )

            # Update data:
            if deadline < now:
                move_db[default_code]['deadlined'] = True
                deadline_text = ' [CADUCADO]'
            else:
                deadline_text = ''
            move_db[default_code]['total'] += move.quantity

            move_db[default_code]['comment'] += 'Q. %s%s: %s > %s (%s)%s\n' % (
                move.quantity,
                uom,
                move.name,
                str(move.deadline)[:10],
                move.partner_name,
                deadline_text,
                )

        # ---------------------------------------------------------------------
        #                          Excel export:
        # ---------------------------------------------------------------------
        order_col = 7
        parameters = {
            'width': 500,
            }
        # Setup:
        header = [
            u'Tipo',

            u'Codigo', u'Descripcion', u'UM',
            u'Appr.', u'Mod.',
            u'Invent. actual', u'Disponibilidad bruta', u'Status',

            u'Manual',
            u'Tiempo de Entrega',
            u'Promedio Kg/Mes',

            u'Nivel Minimo Dias', u'Nivel Minimo Kg.',
            u'Nivel Maximo Dia', u'Nivel Maximo Kg.',
            # u'Obsolete',
            ]

        width = [
            10,
            15, 30, 5,
            6, 9,
            10, 10, 12,
            5, 8, 8,
            8, 8,
            8, 8,
            # 6,
            ]

        # ---------------------------------------------------------------------
        # Create WS:
        # ---------------------------------------------------------------------
        ws_not_present = 'Sin Movimentos'
        gap = 0.000001
        ws_list = (
            (
                'ROP',
                [('medium_stock_qty', '>', gap)],  # todo remove domain not use
                # test:
                'product.medium_stock_qty > 0.0 and not product.not_in_status',
                ),
            # ('Niveles Manuales', [
            #    ('manual_stock_level', '=', True),
            #    # ('min_stock_level', '>', 0),
            #    ]),
            (
                ws_not_present,
                [],  # [('medium_stock_qty', '<=', gap)],   # todo remove
                # test:
                'product.min_stock_level <= 0.0 or product.not_in_status',
                ),
            )
        # Create all pages:
        excel_format = {}
        removed_ids = []

        ws_name = 'ROP'
        excel_pool.create_worksheet(name=ws_name)

        excel_pool.column_width(ws_name, width)
        # excel_pool.row_height(ws_name, row_list, height=10)
        excel_pool.freeze_panes(ws_name, 1, 2)
        excel_pool.column_hidden(ws_name, [4, 5, 10])

        # -----------------------------------------------------------------
        # Generate format used (first time only):
        # -----------------------------------------------------------------
        excel_pool.set_format(header_size=10, text_size=10)
        excel_format['title'] = excel_pool.get_format(key='title')
        excel_format['header'] = excel_pool.get_format(key='header')
        excel_format['header_wrap'] = excel_pool.get_format(
            key='header_wrap')
        excel_format['text'] = excel_pool.get_format(key='text')
        excel_format['right'] = excel_pool.get_format(key='text_right')
        excel_format['number'] = excel_pool.get_format(key='number')

        excel_format['white'] = {
            'text': excel_pool.get_format(key='text'),
            'right': excel_pool.get_format(key='text_right'),
            'number': excel_pool.get_format(key='number'),
        }
        excel_format['orange'] = {
            'text': excel_pool.get_format(key='bg_orange'),
            'right': excel_pool.get_format(key='bg_orange_right'),
            'number': excel_pool.get_format(key='bg_orange_number'),
        }
        excel_format['yellow'] = {
            'text': excel_pool.get_format(key='bg_yellow'),
            'right': excel_pool.get_format(key='bg_yellow_right'),
            'number': excel_pool.get_format(key='bg_yellow_number'),
        }
        excel_format['red'] = {
            'text': excel_pool.get_format(key='bg_red'),
            'right': excel_pool.get_format(key='bg_red_right'),
            'number': excel_pool.get_format(key='bg_red_number'),
        }
        excel_format['grey'] = {
            'text': excel_pool.get_format(key='bg_grey'),
            'right': excel_pool.get_format(key='bg_grey_right'),
            'number': excel_pool.get_format(key='bg_grey_number'),
        }

        # -----------------------------------------------------------------
        # Write title / header
        # -----------------------------------------------------------------
        row = 0
        excel_pool.write_xls_line(
            ws_name, row, header,
            default_format=excel_format['header_wrap'])
        excel_pool.autofilter(ws_name, row, row, 0, len(header) - 1)
        excel_pool.row_height(ws_name, [row], height=38)
        row += 1  # Jump header
        hidden_row = []
        for mode, product_filter, test in ws_list:
            # -----------------------------------------------------------------
            # Product selection:
            # -----------------------------------------------------------------
            # product_filter = [] # overridden (product_filter will be removed)
            product_ids = product_pool.search(
                cr, uid, product_filter, context=context)

            if mode == ws_not_present and removed_ids:
                # Add also removed from other loop
                product_ids = list(set(product_ids).union(set(removed_ids)))

            products = product_pool.browse(
                cr, uid, product_ids,
                context=context)

            # todo add also package data!!!
            for product in sorted(products, key=lambda x: (
                    self.get_type(x), x.default_code)):
                # Field used:
                default_code = product.default_code
                account_qty = int(product.accounting_qty)

                if mode == ws_not_present:
                    save_log(
                        'pre_not_used',
                        '>> %s|%s|%s' % (mode, default_code, account_qty),
                    )

                if not eval(test):
                    continue

                # Filter code:
                if not default_code:
                    _logger.error('Product %s has no code' % product.name)
                    continue
                product_type = self.get_type(product)

                # Remove REC and SER product (go in last page):
                if mode != ws_not_present and product_type == 'REC' or \
                        default_code.startswith('SER'):
                    removed_ids.append(product.id)
                    continue

                # Supplier Order data:
                order_data = move_db.get(default_code, {})
                order_account_qty = order_data.get('total', 0.0)
                order_comment = order_data.get('comment', '')
                order_deadlined = order_data.get('deadlined', '')

                order_account_qty += int(account_qty + 0.0)  # todo get order!
                min_stock_level = int(product.min_stock_level)
                if mode == ws_not_present:
                    state = _(u'Sin movimentos')
                    color_format = excel_format['grey']
                elif account_qty < min_stock_level < order_account_qty:
                    state = _(u'En cobertura')
                    color_format = excel_format['yellow']
                elif account_qty < min_stock_level:
                    state = _(u'Bajo Nivel')
                    color_format = excel_format['orange']
                elif account_qty < 0:
                    state = _(u'Negativo')
                    color_format = excel_format['red']
                else:
                    state = _('OK')
                    color_format = excel_format['white']

                if order_deadlined:
                    color_order_account_qty = (
                        order_account_qty, excel_format['red']['right'])
                else:
                    color_order_account_qty = (
                        order_account_qty, color_format['right'])
                line = [
                    product_type,
                    default_code or '',
                    product.name or '',
                    product.uom_id.name or '',

                    (product.approx_integer, color_format['right']),
                    product.approx_mode or '',

                    (account_qty, color_format['right']),
                    color_order_account_qty,
                    state,

                    (product.manual_stock_level or '', color_format['right']),
                    product.day_leadtime or '',
                    # per month:
                    (product.medium_stock_qty * 30, color_format['number']),

                    (product.day_min_level, color_format['right']),
                    (int(min_stock_level), color_format['right']),

                    (product.day_max_level, color_format['right']),
                    (int(product.max_stock_level), color_format['right']),

                    # 'X' if product.stock_obsolete else '',
                    ]

                excel_pool.write_xls_line(
                    ws_name, row, line, default_format=color_format['text'])
                if product_type == 'EXCL':
                    hidden_row.append(row)

                # -------------------------------------------------------------
                # Logging mode:
                # -------------------------------------------------------------
                if mode == ws_not_present:
                    save_log(
                        'not_used',
                        '>> %s|%s|%s' % (mode, default_code, account_qty),
                    )
                else:
                    save_log(
                        'used',
                        '>> %s|%s|%s' % (mode, default_code, account_qty),
                    )

                if order_comment:
                    excel_pool.write_comment(
                        ws_name, row, order_col, order_comment,
                        parameters=parameters)
                row += 1

        # Hidden row:
        if hidden_row:
            excel_pool.filter_column_list(ws_name, 'A', [
                'IT', 'COMP', 'MP', 'PT', 'REC',
            ])
            # excel_pool.preset_filter_column(ws_name, 'A', 'x != "EXCL"')
            excel_pool.row_hidden(ws_name, hidden_row)

        if save_mode:
            return excel_pool.save_file_as(save_mode)
        else:
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
            MX Mode:
        """
        _logger.info('Updating medium from MRP (final product) MX')
        # todo 27/06/2025: jump this procedure, maybe is obsolete!
        return super(MrpProductionWorkcenterLineOverride, self).update_product_level_from_production(
            cr, uid, ids, context=context)

        # ==============================================================================================================
        # RIMOSSA QUESTA PARTE SOTTO !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # ==============================================================================================================
        company_pool = self.pool.get('res.company')
        load_pool = self.pool.get('mrp.production.workcenter.load')
        # product_pool = self.pool.get('product.product')

        # Get parameters:
        company_ids = company_pool.search(cr, uid, [], context=context)
        company = company_pool.browse(cr, uid, company_ids, context=context)[0]
        stock_level_days = company.stock_level_days
        if not stock_level_days:
            raise osv.except_osv(
                _('Error stock management'),
                _('Setup the parameter in company form'),
                )
        # MRP stock level extra parameters:
        mrp_stock_level_mp = company.mrp_stock_level_mp or stock_level_days
        mrp_stock_level_pf = company.mrp_stock_level_pf or stock_level_days
        # mrp_stock_level_force (for product)

        now = datetime.now()
        date_limit = {
            # statistic period from keep MRP production:
            'now': self.get_form_date(now, 0),
            'mrp': self.get_form_date(now, stock_level_days),

            'material': self.get_form_date(now, mrp_stock_level_mp),
            'product': self.get_form_date(now, mrp_stock_level_pf),
        }
        # Update with particular product
        self.get_product_stock_days_force(cr, uid, date_limit, context=context)

        load_ids = load_pool.search(cr, uid, [
            # ('date', '>=', date_limit['mrp']),  # remove for hide old prod.
            ('date', '<', date_limit['now']),
            ('recycle', '=', False),
            ], context=context)

        _logger.warning('Load found: %s Period: [>=%s <%s]' % (
            len(load_ids),
            date_limit['mrp'],
            date_limit['now'],
            ))

        product_obsolete = {}
        product_medium = {}
        log_f = open(os.path.expanduser('~/pf_load.csv'), 'w')
        log_f.write('Modo|Data|MRP|ID|Code|Q.|Obs\n')
        for load in load_pool.browse(cr, uid, load_ids, context=context):
            date = load.date

            # ----------------------------------------------------------------------------------------------------------
            # Load Product:
            # ----------------------------------------------------------------------------------------------------------
            product = load.product_id  # production_id.product_id
            if product not in product_obsolete:
                product_obsolete[product] = True  # Default obsolete

            # Check product obsolete (partic or default):
            if date < date_limit.get('product', date_limit['product']):
                # Obsolete Job, not considered
                continue

            product_obsolete[product] = False

            quantity = load.product_qty
            if product in product_medium:
                product_medium[product] += quantity
            else:
                product_medium[product] = quantity

            # ----------------------------------------------------------------------------------------------------------
            # Recycle:
            # ----------------------------------------------------------------------------------------------------------
            # recycle_product_id  # TODO not used

            # ----------------------------------------------------------------------------------------------------------
            # Package:
            # ----------------------------------------------------------------------------------------------------------
            product = load.package_id.linked_product_id
            if product not in product_obsolete:
                product_obsolete[product] = True  # Set as default obsolete

            # Check product obsolete (partic. or default):
            if date > date_limit.get('product', date_limit['product']):
                product_obsolete[product] = False

            quantity = load.ul_qty
            if product and quantity:
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity

            # ----------------------------------------------------------------------------------------------------------
            # Pallet:
            # ----------------------------------------------------------------------------------------------------------
            product = load.pallet_product_id
            if product not in product_obsolete:
                product_obsolete[product] = True  # Default obsolete

            # Check product obsolete (partic. or default):
            if date > date_limit.get('product', date_limit['product']):
                product_obsolete[product] = False

            quantity = load.pallet_qty
            if product and quantity:
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity

            # Log file:
            log_f.write('%s|%s|%s|%s|%s|%s\n' % (
                date,
                load.production_id.name,
                load.product_id.id,
                load.product_id.default_code or '',
                load.product_qty,
                date > date_limit.get('product', date_limit['product']),
            ))

        # Update medium in product:
        self.update_product_medium_from_dict(
            cr, uid, product_medium, stock_level_days, product_obsolete,  # manage obsolete in this function,
            context=context)

        # Call original method for raw materials:
        return super(MrpProductionWorkcenterLineOverride, self).update_product_level_from_production(
            cr, uid, ids, context=context)
