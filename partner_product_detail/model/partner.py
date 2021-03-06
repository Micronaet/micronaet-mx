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


class ResPartnerPpricelistProduct(orm.Model):
    ''' Class for manage particularity for partner - product
    '''    
    _name = 'res.partner.pricelist.product'
    _description = 'Partner product'
    _rec_name = 'product_id'
    _order = 'product_id'

    _columns = {
        'product_id': fields.many2one('product.product', 'Product'),
        'alias_id': fields.many2one('product.product', 'Alias'),

        'date': fields.date('Date'),
        'deadline': fields.date('Deadline'),
        #'sell': fields.boolean('Sell rule'),
        #'cost': fields.float('Cost', digits=(16, 2)), # for purchase?
        'price': fields.float('Price', digits=(16, 2)),
        # TODO Currency
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'note': fields.text('Note'),
            
        'packaging_id': fields.many2one('product.packaging', 'Packaging', 
            ondelete='set null'),
        # ---------------------------------------------------------------------
        # TODO used for calculate packaging? XXX not used for now
        'product_ul': fields.many2one('product.ul', 'Pack', 
            ondelete='set null'),
        'load_qty': fields.float('Load q.ty', digits=(16, 2)),            
        # ---------------------------------------------------------------------
        }

    _defaults = {
        'date': lambda *a: datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT),
        }

class ResPartner(orm.Model):
    ''' Class partner
    '''    
    _inherit = 'res.partner'
    
    _columns = {
        'pricelist_product_ids': fields.one2many(
            'res.partner.pricelist.product', 'partner_id', 
            'Pricelist products'),
        }

class SaleOrderLine(orm.Model):
    ''' Add event for onchange in sale.order.line
    '''    
    _inherit = 'sale.order.line'
    
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False, 
            fiscal_position=False, flag=False, context=None):
        ''' Override function for set up extra fields as partner customization
        '''    
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
                'alias_id': False,                
                'price_unit': False,
                'product_packaging': False,
                'load_qty': False, # XXX remove?
                # TODO
                })
            return res
        
        # Used pool:
        partner_pool = self.pool.get('res.partner')
        
        # Udpate field instead:
        partner_proxy = partner_pool.browse(
            cr, uid, partner_id, context=context)
            
        for item in partner_proxy.pricelist_product_ids:
            if item.product_id.id == product:
                res['value'].update({
                    'alias_id': item.alias_id.id,
                    'price_unit': item.price,
                    # TODO use first if not present in customization?
                    'product_packaging': item.packaging_id.id, 
                    'load_qty': item.load_qty, #XXX remove?
                    })
        return res
    
    _columns = {
        # TODO remove?
        'load_qty': fields.float('Load q.ty', digits=(16, 2)),            
        }        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
