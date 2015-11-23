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

class SaleOrder(orm.Model):
    ''' Extra field for order
    '''    
    _inherit = 'sale.order'
    
    # -------------------------------------------------------------------------
    #                                  Override:
    # -------------------------------------------------------------------------
    # onchange:
    
    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        ''' Override standard procedure for add extra account field:        
        '''
        # Call original procedure:
        res = super(SaleOrder, self).onchange_partner_id(
            cr, uid, ids, partner_id, context=context)
        if 'value' not in res:
            res['value'] = {}
        
        # Append extra value:
        if not partner_id: # reset:
            res['value'].update({
                'incoterm': False,                
                'default_transport_id': False,
                'carriage_condition_id': False,
                'goods_description_id': False,
                'transportation_reason_id': False,
                'payment_term_id': False,
                'bank_account_id': False,
                'uncovered_payment': False,
                })
            return res

        partner_pool = self.pool.get('res.partner')
        partner_proxy = partner_pool.browse(cr, uid, partner_id, 
            context=context)
        
        res['value'].update({
            #'incoterm': partner_proxy.incoterm,
            'default_transport_id': partner_proxy.default_transport_id.id,
            'carriage_condition_id': partner_proxy.carriage_condition_id.id,
            'goods_description_id': partner_proxy.goods_description_id.id,
            'transportation_reason_id': 
                partner_proxy.transportation_reason_id.id,
            'payment_term_id': partner_proxy.property_payment_term.id,            
            
            # Alert:
            'uncovered_payment': partner_proxy.duelist_uncovered,
            })
        # Set default account for partner    
        if partner_proxy.bank_ids:
            res['value']['bank_account_id'] = partner_proxy.bank_ids[0].id
            
        return res

    _columns = {
        # moved here from production:
        'date_deadline': fields.date('Deadline', 
            help='If all order has same deadline set only in header'),
        'date_load': fields.date('Load date', 
            help='Load date'),
        'date_previous_deadline': fields.date(
            'Previous deadline', 
            help="If during sync deadline is modified this field contain old "
                "value before update"),
        'date_delivery': fields.date('Delivery', help="Contain delivery date, when present production plan work with this instead of deadline value, if forced production cannot be moved"),
        # moved ^^^^^^^^^^^^^^^^^^^^^
        
        # Account extra field saved in sale.order:
        'default_transport_id': fields.many2one('res.partner', 'Vector', 
            domain=[('is_vector', '=', True)]),
        'carriage_condition_id': fields.many2one(
            'stock.picking.carriage_condition', 'Carriage condition'),
        'goods_description_id': fields.many2one(
            'stock.picking.goods_description', 'Goods description'),
        'transportation_reason_id': fields.many2one(
            'stock.picking.transportation_reason', 'Transportation reason'),
        'payment_term_id': fields.many2one(
            'account.payment.term', 'Payment term'),            
        'bank_account_id': fields.many2one(
            'res.partner.bank', 'Bank account'),
        
        # Alert:
        'uncovered_payment': fields.boolean('Uncovered payment'),    
        'uncovered_alert': fields.char('Alert', size=64, readonly=True), 
        }
        
    _defaults = {
        'uncovered_alert': lambda *x: 'Alert: Uncovered payment!!!',
        }   
     

class SaleOrderLine(orm.Model):
    ''' Extra field for order line
    '''
    
    _inherit = 'sale.order.line'
    
    # ----------------
    # Function fields:
    # ----------------
    def _function_get_delivered(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate delivered elements in picking orders
        '''
        res = {}
        move_pool = self.pool.get('stock.move')
        
        for line in self.browse(cr, uid, ids, context=context):            
            res[line.id] = 0.0
            move_ids = move_pool.search(cr, uid, [
                ('sale_line_id', '=', line.id)], context=context)                
            for move in move_pool.browse(cr, uid, move_ids, context=context):
                if move.picking_id.ddt_number: # was marked as DDT
                    # TODO check UOM!!! for 
                    res[line.id] += move.product_qty
        return res
        
    _columns = {
        'gr_weight': fields.float('Gross weight'),
        #states={'draft': [('readonly', False)]}),
        
         # Moved here from production:
        'date_deadline': fields.date('Deadline'),
        'date_delivery':fields.related(
            'order_id', 'date_delivery', type='date', string='Date delivery'),
            
        # TODO Note: there's yet product.package that is a sort of UL    
        'product_ul_id':fields.many2one(
            'product.ul', 'Required package', ondelete='set null'),
        # Moved here ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

        'alias_id':fields.many2one(
            'product.product', 'Alias product', ondelete='set null'),

        'delivered_qty': fields.function(
            _function_get_delivered, method=True, type='float', readonly=True,
            string='Delivered', store=False, 
            help='Quantity delivered with DDT out'),
            
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
