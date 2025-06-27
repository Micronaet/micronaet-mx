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


class MrpProductionWorkcenterLine(osv.osv):
    """ Model name: Job
    """

    _inherit = 'mrp.production.workcenter.line'

    def get_product_stock_days_force(self, cr, uid, data, context=None):
        """ Extract product if exist particularity for stock level days forced
        """
        now = datetime.now()
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('mrp_stock_level_force', '>', 0),
        ], context=context)
        for product in product_pool.browse(cr, uid, product_ids, context=context):
            data[product] = self.get_form_date(now, product.mrp_stock_level_force)
        return True

    # 18/03/2024 Overridden in Sapnaet
    def update_product_medium_from_dict(
            self, cr, uid, product_medium, stock_level_days, product_obsolete, context=None):
        """ Upload product with dictionary loaded:
            product_obsolete: Not used for now in ID (mark product as obsolete)
            context parameters: clean_remain  >>  Reset all remain product m(x)
        """
        if context is None:
            context = {}
        clean_remain = context.get('clean_remain')

        product_pool = self.pool.get('product.product')
        _logger.warning('Product found: %s' % len(product_medium))

        os.system('mkdir -p %s' % os.path.expanduser('~/log/medium'))
        log_f = open(os.path.expanduser('~/log/medium/medium.csv'), 'w')
        log_f.write('ID|Codice|Totale periodo|Giorni periodo|Media|Obsoleto\n')

        done_product_ids = []
        for product in product_medium:
            done_product_ids.append(product.id)
            total = product_medium[product]
            if product.manual_stock_level:
                continue

            if not total:
                medium_stock_qty = 0.0
            else:
                medium_stock_qty = total / stock_level_days

            log_f.write('%s|%s|%s|%s|%s|%s\n' % (
                product.id,
                product.default_code,
                total,
                stock_level_days,
                medium_stock_qty,
                product_obsolete.get(product, False)
            ))
            product_pool.write(cr, uid, [product.id], {
                'medium_origin': 'mrp',
                'medium_stock_qty': medium_stock_qty,
                'min_stock_level': product.day_min_level * medium_stock_qty,
                # product_pool.round_integer_order(
                #    product.day_min_level * medium_stock_qty,
                #    approx=product.approx_integer,
                #    mode=product.approx_mode),
                'max_stock_level': product.day_max_level * medium_stock_qty,
                # product_pool.round_integer_order(
                #    product.day_max_level * medium_stock_qty,
                #    approx=product.approx_integer,
                #    mode=product.approx_mode),
                'ready_stock_level': product.day_max_ready_level * medium_stock_qty,
                # product_pool.round_integer_order(
                #    product.day_max_ready_level * medium_stock_qty,
                #    approx=product.approx_integer,
                #    mode=product.approx_mode),
                # todo not used for now:
                # 'stock_obsolete': product_obsolete.get(product, False),
            }, context=context)

        if clean_remain:
            product_ids = product_pool.search(cr, uid, [
                ('id', 'not in', done_product_ids),
            ], context=context)

            _logger.warning('Clean remain product resetting medium (# %s' % len(product_ids))
            product_pool.write(cr, uid, product_ids, {
                'medium_origin': False,
                'medium_stock_qty': False,
                'min_stock_level': False,
                'max_stock_level': False,
                'ready_stock_level': False,
            }, context=context)

        log_obs_f = open(os.path.expanduser('~/log/medium/obsolete.csv'), 'w')
        log_obs_f.write('ID|Codice\n')

        # Clean and mark as obsolete the dict passed
        for product in product_obsolete:
            try:
                is_obsolete = product_obsolete[product]
                product_id = product.id
                if type(product_id) != int:
                    continue
            except:
                continue

            if is_obsolete:
                product_pool.write(cr, uid, [product.id], {
                    'medium_origin': 'mrp',
                    'medium_stock_qty': False,
                    'min_stock_level': False,
                    'max_stock_level': False,
                    'ready_stock_level': False,
                    'stock_obsolete': True,
                }, context=context)

                log_obs_f.write('%s|%s\n' % (
                    product.id,
                    product.default_code,
                ))
        return True

    def get_form_date(self, now, days):
        """ Utility: Generate text date for evaluation
        """
        from_dt = now - timedelta(days=days)
        return '%s 00:00:00' % from_dt.strftime(DEFAULT_SERVER_DATE_FORMAT)

    # Note: 18/03/2024 Overridden from Sapnaet Module
    def update_product_level_from_production_IT(self, cr, uid, context=None):
        """ Update product level from production (only raw materials)
            No obsolete management
            05/03/2022
            NOTE: This procedure was duplicated from:
            update_product_level_from_production because original procedure
            was a mix of logic from IT to MX so it's not valid from Italy
        """
        _logger.info('Updating medium from MRP (raw material)')
        company_pool = self.pool.get('res.company')
        load_pool = self.pool.get('mrp.production.workcenter.load')
        # Unload from: mrp.production.workcenter.line

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

        # ---------------------------------------------------------------------
        # MRP stock level extra parameters (obsolete product manage):
        # ---------------------------------------------------------------------
        # Force parameter or used default master days:
        mrp_stock_level_mp = company.mrp_stock_level_mp or stock_level_days
        mrp_stock_level_pf = company.mrp_stock_level_pf or stock_level_days

        now = datetime.now()
        date_limit = {
            # statistic period from keep MRP production:
            'now': self.get_form_date(now, 0),
            'mrp': self.get_form_date(now, stock_level_days),

            'material': self.get_form_date(now, mrp_stock_level_mp),
            'product': self.get_form_date(now, mrp_stock_level_pf),
        }
        # MRP stock level extra parameters: (product param force company)
        self.get_product_stock_days_force(cr, uid, date_limit, context=context)

        # ---------------------------------------------------------------------
        #                             RAW MATERIALS:
        # ---------------------------------------------------------------------
        job_ids = self.search(cr, uid, [
            ('real_date_planned', '>=', date_limit['mrp']),
            ('real_date_planned', '<', date_limit['now']),
            ], context=context)
        _logger.warning('Job (for material) found: %s Period: [>=%s <%s]' % (
            len(job_ids),
            date_limit['mrp'],
            date_limit['now'],
            ))

        product_obsolete = {}
        product_medium = {}

        # Log files:
        os.system('mkdir -p %s' % os.path.expanduser('~/log/medium'))
        log_f = open(os.path.expanduser('~/log/medium/unload.csv'), 'w')
        log_f.write('ID|Code|Job|MRP|Date\n')
        for job in self.browse(cr, uid, job_ids, context=context):
            date = job.real_date_planned
            for material in job.bom_material_ids:
                product = material.product_id
                default_code = product.default_code
                if default_code[0] not in 'AB':  # is product not material!
                    _logger.error(
                        'Not used, unload product: %s' % default_code)
                    continue
                if product not in product_obsolete:
                    product_obsolete[product] = True  # Default obsolete

                # Check product obsolete (partics or default):
                if date > date_limit.get(product, date_limit['material']):
                    product_obsolete[product] = False

                quantity = material.quantity
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity
                log_f.write('%s|%s|%s|%s|%s\n' % (
                    product.id,
                    product.default_code,
                    job.name,
                    job.production_id.name,
                    job.real_date_planned,
                ))

        # --------------------------------------------------------------------------------------------------------------
        #                            FINAL PRODUCT:
        # --------------------------------------------------------------------------------------------------------------
        load_ids = load_pool.search(cr, uid, [
            ('date', '>=', date_limit['mrp']),
            ('date', '<', date_limit['now']),
            ], context=context)
        _logger.warning('Load (for final product) #: %s Period: [>=%s <%s]' % (
            len(job_ids),
            date_limit['mrp'],
            date_limit['now'],
            ))
        # Note keep same dict of material for collect data and obsolete!
        os.system('mkdir -p %s' % os.path.expanduser('~/log/medium'))
        log_f = open(os.path.expanduser('~/log/medium/load.csv'), 'w')
        log_f.write('ID|Codice|CL|Data|Mode\n')
        for load in load_pool.browse(cr, uid, load_ids, context=context):
            date = load.date
            data_list = (
                # Load product:
                (load.product_id, load.product_qty, 'load'),
                # Unload pack:
                (load.package_id.linked_product_id, load.ul_qty, 'unload'),
                # Unload pallet:
                (load.pallet_product_id, load.pallet_qty, 'unload'),
                )
            for product, product_qty, mode in data_list:
                if not product or product_qty <= 0:
                    continue
                default_code = product.default_code

                if default_code[0] == 'A':  # not raw material but package yes
                    _logger.error(
                        'Not used raw material: %s' % default_code)
                    continue

                # Obsolete check:
                if product not in product_obsolete:
                    product_obsolete[product] = True  # Default obsolete

                # Check product obsolete (partic. or default):
                if date > date_limit.get(product, date_limit['product']):
                    product_obsolete[product] = False

                if product in product_medium:
                    product_medium[product] += product_qty
                else:
                    product_medium[product] = product_qty
                log_f.write('%s|%s|%s|%s|%s\n' % (
                    product.id,
                    product.default_code,
                    load.accounting_cl_code,
                    date,
                    mode,
                ))

        # Italy procedure:
        return self.update_product_medium_from_dict(
            cr, uid, product_medium, stock_level_days, product_obsolete, context=context)

    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Update product level from production (only raw materials, package and pallet from SL document)
            No obsolete management

            05/03/2022
            NOTE: This procedure was kept but maybe is used only in MX:
                  Use new procedure created for IT: update_product_level_from_production_it
        """
        if context is None:
            context = {}

        _logger.info('Updating medium from MRP (raw material only) MX Procedure!')
        company_pool = self.pool.get('res.company')

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

        now = datetime.now()
        date_limit = {
            # statistic period from keep MRP production:
            'now': self.get_form_date(now, 0),
            'mrp': self.get_form_date(now, stock_level_days),

            'material': self.get_form_date(now, mrp_stock_level_mp),
            'product': self.get_form_date(now, mrp_stock_level_pf),
        }

        # Product force parameters:
        self.get_product_stock_days_force(cr, uid, date_limit, context=context)

        job_ids = self.search(cr, uid, [
            ('real_date_planned', '>=', date_limit['mrp']),
            ('real_date_planned', '<', date_limit['now']),
            ], context=context)
        _logger.warning('Job found: %s Period: [>=%s <%s]' % (
            len(job_ids),
            date_limit['mrp'],
            date_limit['now'],
            ))

        product_obsolete = {}
        product_medium = {}

        # Log to file:
        os.system('mkdir -p %s' % os.path.expanduser('~/log/medium'))
        log_f = open(os.path.expanduser('~/log/medium/unload.csv'), 'w')
        log_pack_f = open(os.path.expanduser('~/log/medium/unload_pack.csv'), 'w')

        # Header:
        log_f.write('ID|Code|Job|MRP|Date|Q.\n')
        log_pack_f.write('ID|Code|Job|MRP|Date|Q.\n')
        for job in self.browse(cr, uid, job_ids, context=context):
            date = job.real_date_planned

            # ----------------------------------------------------------------------------------------------------------
            # Unload material from SL:
            # ----------------------------------------------------------------------------------------------------------
            for material in job.bom_material_ids:
                product = material.product_id
                default_code = product.default_code or ' '
                if product.product_type == 'PT':
                    _logger.error('Not used, unload product: %s' % default_code)
                    continue

                # Mark as obsolete always (remove if used after!)
                if product not in product_obsolete:
                    product_obsolete[product] = True  # Default obsolete

                # Check product obsolete (partic. or default):
                if date > date_limit.get(product, date_limit['material']):
                    product_obsolete[product] = False

                quantity = material.quantity
                if product in product_medium:
                    product_medium[product] += quantity
                else:
                    product_medium[product] = quantity

                log_f.write('%s|%s|%s|%s|%s|%s\n' % (
                    product.id,
                    product.default_code,
                    job.name,
                    job.production_id.name,
                    job.real_date_planned,
                    quantity,
                ))

            # ----------------------------------------------------------------------------------------------------------
            # Unload package and pallet from CL:
            # ----------------------------------------------------------------------------------------------------------
            for cl in job.load_ids:
                # A. Package:
                try:
                    package = cl.package_id.linked_product_id
                    package_qty = cl.ul_qty
                    if package and package_qty:
                        if package in product_medium:
                            product_medium[package] += package_qty
                        else:
                            product_medium[package] = package_qty

                        log_pack_f.write('%s|%s|%s|%s|%s|%s\n' % (
                            package.id,
                            package.default_code,
                            job.name,
                            job.production_id.name,
                            job.real_date_planned,
                            package_qty,
                        ))
                except:
                    _logger.error('Error checking package product')

                # B. Pallet:
                pallet = cl.pallet_product_id
                pallet_qty = cl.pallet_qty
                if pallet and pallet_qty:
                    if pallet in product_medium:
                        product_medium[pallet] += pallet_qty
                    else:
                        product_medium[pallet] = pallet_qty

                    log_pack_f.write('%s|%s|%s|%s|%s|%s\n' % (
                        pallet.id,
                        pallet.default_code,
                        job.name,
                        job.production_id.name,
                        job.real_date_planned,
                        pallet_qty,
                    ))

        return self.update_product_medium_from_dict(
            cr, uid, product_medium, stock_level_days, product_obsolete, context=context)


class ResCompany(osv.osv):
    """ Model name: Parameters
    """

    _inherit = 'res.company'

    def extract_product_level_xlsx(self, cr, uid, ids, context=None):
        """ Extract current report stock level
            @context parameter:
                save_mode: fullname for XLSX file generated instead of returned
        """
        if context is None:
            context = {}
        save_mode = context.get('save_mode')

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
            'Min Gest.', 'Max Gest.',

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
            ('Prod. Livelli auto', [
                ('manual_stock_level', '=', False),
                ('medium_stock_qty', '>', 0),
                ],
             '(default_code or " ")[0] not in "AB"',
             ),
            ('Prod. Livelli manuali', [
                ('manual_stock_level', '=', True),
                # ('min_stock_level', '>', 0),
                ],
             '(default_code or " ")[0] not in "AB"',
             ),
            ('Prod. Non presenti', [
                ('min_stock_level', '<=', 0),
                ],
             '(default_code or " ")[0] not in "AB"',

             ),

            ('Mat. Livelli auto', [
                ('manual_stock_level', '=', False),
                ('medium_stock_qty', '>', 0),
                ],
             '(default_code or " ")[0] in "AB"',
             ),
            ('Mat. Livelli manuali', [
                ('manual_stock_level', '=', True),
                # ('min_stock_level', '>', 0),
                ],
             '(default_code or " ")[0] in "AB"',
             ),
            ('Mat. Non presenti', [
                ('min_stock_level', '<=', 0),
                ],
             '(default_code or " ")[0] in "AB"',
             ),
            )
        # Create all pages:
        excel_format = {}
        for ws_name, product_filter, code_filter in ws_list:
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

            product = product_pool.browse(
                cr, uid, product_ids,
                context=context)

            row += 1
            for product in sorted(product, key=lambda x: x.default_code):
                default_code = product.default_code
                if not eval(code_filter):  # Post filter (not used in domain)
                    continue
                line = [
                    default_code or '',
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
        if save_mode:
            return excel_pool.save_file_as(save_mode)
        else:
            return excel_pool.return_attachment(
                cr, uid, 'Livelli prodotto', 'livelli_magazzino.xlsx',
                version='7.0', php=True, context=context)

    def update_product_level_from_production(self, cr, uid, ids, context=None):
        """ Button from company
        """
        return self.pool.get('mrp.production.workcenter.line'
            ).update_product_level_from_production(cr, uid, ids, context=context)

    def update_product_level_from_production_IT(
            self, cr, uid, ids, context=None):
        """ Button from company
        """
        return self.pool.get('mrp.production.workcenter.line'
            ).update_product_level_from_production_IT(cr, uid, context=context)

    _columns = {
        'stock_level_days': fields.integer(
            'Stock level days', help='Days for from data till today'),

        # Used only in MX:
        'mrp_stock_level_mp': fields.integer(
            'MRP MP obsolete',
            help='Days to consider obsolete raw material'),
        'mrp_stock_level_pf': fields.integer(
            'MRP FP obsolete',
            help='Days to consider obsolete final product'),

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


