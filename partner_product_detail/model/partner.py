# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    Original module for stock.move from:
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import pdb
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
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


class ResPartnerPricelistProduct(orm.Model):
    """ Class for manage particularity for partner - product
    """
    _name = 'res.partner.pricelist.product'
    _description = 'Partner product'
    _rec_name = 'product_id'
    _order = 'product_id'

    _columns = {
        'product_id': fields.many2one('product.product', 'Dare'),
        # 22/03/2024: Non più utilizzata su richiesta Cassandra
        'alias_id': fields.many2one('product.product', 'Alias'),
        'alias_name': fields.char(
            'Descriz. prodotto', size=50,
            help='Forzatura testuale del prodotto alias qualora non esistesse'
                 'il prodotto fisico',
        ),
        'date': fields.date('Data'),
        'deadline': fields.date('Scadenza'),
        # 'sell': fields.boolean('Sell rule'),
        # 'cost': fields.float('Cost', digits=(16, 2)), # for purchase?
        'price': fields.float('Prezzo', digits=(16, 2)),
        # todo Currency
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'note': fields.text('Note'),

        'pallet_weight': fields.integer(
            'Max pallet',
            help='Indica il peso massimo a cui caricare il pallet '
                 'quando si prepara per questo prodotto'),
        'packaging_id': fields.many2one(
            'product.packaging', 'Imballo',
            ondelete='set null'),
        # ---------------------------------------------------------------------
        # todo used for calculate packaging? XXX not used for now
        'product_ul': fields.many2one(
            'product.ul', 'Pack',
            ondelete='set null'),
        'load_qty': fields.float('Load q.ty', digits=(16, 2)),
        # ---------------------------------------------------------------------
        }

    _defaults = {
        'date': lambda *a: datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT),
        }


class ResPartner(orm.Model):
    """ Class partner
    """
    _inherit = 'res.partner'

    _columns = {
        'pricelist_product_ids': fields.one2many(
            'res.partner.pricelist.product', 'partner_id',
            'Pricelist products'),
        }


class SaleOrderLine(orm.Model):
    """ Add event for onchange in sale.order.line
    """
    _inherit = 'sale.order.line'

    def product_id_change(
            self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False,
            fiscal_position=False, flag=False, context=None):
        """ Override function for set up extra fields as partner customization
        """
        context = context or {}
        res = super(SaleOrderLine, self).product_id_change(
            cr, uid, ids, pricelist=pricelist, product=product, qty=qty,
            uom=uom, qty_uos=qty_uos, uos=uos, name=name,
            partner_id=partner_id, lang=lang, update_tax=update_tax,
            date_order=date_order, packaging=packaging,
            fiscal_position=fiscal_position, flag=flag, context=context)

        if 'value' not in res:
            res['value'] = {}

        # Reset if partner or product not present:
        if not partner_id or not product:
            res['value'].update({
                'name': '',
                # 'alias_id': False,
                'price_unit': False,
                'product_packaging': False,
                'pallet_weight': False,
                'load_qty': False,  # todo remove?
                'tax_id': False
                # todo
                })
            return res

        # Used pool:
        partner_pool = self.pool.get('res.partner')
        product_pool = self.pool.get('product.product')
        fiscal_pool = self.pool.get('account.fiscal.position')

        # Update field instead:
        partner_proxy = partner_pool.browse(
            cr, uid, partner_id, context=context)

        # ---------------------------------------------------------------------
        # Check if order confirm (means no update!)
        # ---------------------------------------------------------------------
        accounting_order = False
        try:
            if ids:
                line = self.browse(cr, uid, ids, context=context)[0]
                order = line.order_id
                accounting_order = order.accounting_order
        except:
            pass  # In case of error consider not confirmed!

        # ---------------------------------------------------------------------
        # VAT Management (patch!):
        # ---------------------------------------------------------------------
        tax_block = False
        if fiscal_position:
            fiscal_id = fiscal_position or \
                        partner_proxy.property_account_position.id
            if fiscal_id:
                fiscal = \
                    fiscal_pool.browse(cr, uid, fiscal_id, context=context)

                try:
                    # tax_id = fiscal.tax_ids[0].tax_dest_id.id
                    tax_id = fiscal.force_account_tax_id.id
                    if tax_id:
                        tax_block = [
                            (6, 0, (tax_id, ))
                            ]
                except:
                    pass

        if tax_block:
            res['value'].update({
                'tax_id': tax_block,
                })
        else:
            _logger.error('No VAT setup for this order!')

        # CASE 1: Update with pricelist partner values:
        data = {}
        if not accounting_order:
            _logger.warning('Order not confirm, so update default data')
            for item in partner_proxy.pricelist_product_ids:
                if item.product_id.id == product:
                    # item.alias_id.name or \
                    name = item.alias_name or item.product_id.name
                    data = {
                        'name': name,
                        # 'alias_id': item.alias_id.id,
                        'price_unit': item.price,
                        # todo use first if not present in customization?
                        'product_packaging': item.packaging_id.id,
                        'pallet_weight':
                            item.pallet_weight or partner_proxy.pallet_weight,
                        # todo also pallet_weight for company if not present?
                        'load_qty': item.load_qty,  # todo remove?
                    }
                    break

        # CASE 2: Product not in partner pricelist:
        # Update name if not present (needed?)
        if 'name' in res['value']:
            # Clean "[code] name" (removed code part)
            data = {
                'name': (res['value']['name'] or '').split('] ')[-1],
            }
        else:
            #    if accounting_order:
            #        del res['value']['name']  # Not updated name
            #else:
            product_proxy = product_pool.browse(
                cr, uid, product, context=context)
            data = {
                'name': (product_proxy.name or '').split('] ')[-1],
            }
            _logger.info('Data: %s' % (data, ))

        # ---------------------------------------------------------------------
        # Update returned values:
        # ---------------------------------------------------------------------
        if data:
            res['value'].update(data)

        if 'warning' in res:
            _logger.error(
                'Remove warning message: \n%s' %
                res['warning'].get('message'))
            del(res['warning'])
        return res

    def set_sale_line_as_default_for_partner(self, cr, uid, ids, context=None):
        """ Default for this partner
        """
        if context is None:
            context = {}
        setup_pool = self.pool.get('res.partner.pricelist.product')

        line = self.browse(cr, uid, ids, context=context)[0]
        partner_id = line.order_id.partner_id.id
        product_id = line.product_id.id

        setup_ids = setup_pool.search(cr, uid, [
            ('partner_id', '=', partner_id),
            ('product_id', '=', product_id),
        ], context=context)
        name = line.name.split(']')[-1].split('\n')[0].strip()

        data = {
            'partner_id': partner_id,
            'product_id': product_id,
            # 'alias_id': line.alias_id.id,
            'alias_name': name if line.product_id.name != name
            else '',
            'price': line.price_unit,
            'pallet_weight': line.pallet_weight,
            'packaging_id': line.product_packaging.id,
            'date': line.create_date,
        }

        if setup_ids:  # Update setup:
            if context.get('force_only_mrp'):  # MRP not update price!
                _logger.warning('Updating only MRP data!')
                del (data['price'])

            setup_pool.write(cr, uid, setup_ids[0], data, context=context)
        else:  # Create new record:
            setup_pool.create(cr, uid, data, context=context)
        return True

    _columns = {
        'pallet_weight': fields.integer(
            'Max pallet',
            help='Indica il peso massimo a cui caricare il pallet '
                 'quando si prepara per questo prodotto'),

        # todo remove?
        'load_qty': fields.float('Load q.ty', digits=(16, 2)),
        }
