# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class SaleDeliveryPartialWizard(orm.TransientModel):
    ''' Wizard for partial delivery on sale
    '''
    _name = 'sale.delivery.partial.wizard'

    # TODO init function for load!
    
    # --------------------
    # Wizard button event:
    # --------------------
    def action_done(self, cr, uid, ids, context=None):
        ''' Event for button done the delivery
        '''
        if context is None: 
            context = {}        
        
        wizard_browse = self.browse(cr, uid, ids, context=context)[0]
        
        # TODO return new order:
        return {
            'type': 'ir.actions.act_window_close'
            }

    def force_deadline_delivery(self, cr, uid, ids, context=None):
        ''' Set up line that have to be delivered depend on date
        '''
        if context is None: 
            context = {}        
        return True    

    _columns = {
        'order_id': fields.many2one('sale.order', 'Order ref.', readonly=True),
        'deadline': fields.date('Deadline', 
            help='Used for force delivery of deadline records'),
        }

class SaleDeliveryPartialLineWizard(orm.TransientModel):
    ''' Temp object for document line
    '''
    _name = 'sale.delivery.partial.line.wizard'

    def set_remain_qty(self, cr, uid, ids, context=None):
        ''' Set remain qty to pick out quantity
        '''
        assert len(ids) == 1, 'Button work only with one record a time!'
        
        item_proxy = self.browse(cr, uid, ids, context=context)[0]
        self.write(cr, uid, ids[0], {
            'delivery_uom_qty': item_proxy.product_remain_qty,
            }, context=context)
        return True # TODO action?
    
    # Field function:
    def _get_delivery_information(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for item in self.pool.get(cr, uid, ids, context=context):
            res[item.id] = {}
            # TODO calculate!!!
            res[item.id]['product_delivered_qty'] = 1.0
            res[item.id]['product_remain_qty'] = 1.0
            
        return res
    
    _columns = {
        # Sale order line reference:
        'wizard_id': fields.many2one('sale.delivery.partial.wizard', 
            'Wizard ref.'),
        'order_line_id': fields.many2one('sale.order.line', 'Order line ref.'),
        'sequence': fields.integer(
            'Sequence', readonly=True,
            help="Gives the sequence order when displaying in list mode."),
        'product_id': fields.many2one(
            'product.product', 'Product', domain=[('sale_ok', '=', True)],
            readonly=True),
        'price_unit': fields.float(
            'Unit Price', digits_compute=dp.get_precision('Product Price'), 
            readonly=True),
        'product_uom_qty': fields.float(
            'Quantity', digits_compute=dp.get_precision('Product UoS'), 
            readonly=True),
        'product_uom': fields.many2one(
            'product.uom', 'Unit of Measure', readonly=True),
        'date_deadline': fields.date('Deadline', readonly=True),        
        
        # Function fields (delivered, invoiced):
        # TODO
        'product_delivered_qty': fields.function(
            _get_delivery_information, method=True, type='float', 
            string='Delivered', store=False, multi=True), 
        'product_remain_qty': fields.function(
            _get_delivery_information, method=True, type='float', 
            string='Remain', store=False, multi=True), 
                        

        # Input fields:
        'delivery_uom_qty': fields.float(
            'Delivery q.', digits_compute=dp.get_precision('Product UoS')),
        }

class SaleDeliveryPartialWizard(orm.TransientModel):
    ''' Add *many fields:
    '''
    _inherit = 'sale.delivery.partial.wizard'
    
    def _load_default_line_ids(self, cr, uid, context=None):
        ''' Load order line as default values
        '''
        sale_pool = self.pool.get('sale.order')
        order_id = context.get('active_id', False)
        if not order_id:
            return False # errotr
        
        sale_proxy = sale_pool.browse(cr, uid, order_id, context)
        res = []
        for line in sale_proxy.order_line:
            res.append((0, False, {
                #'wizard_id': 1,
                'order_line_id': line.id,
                'sequence': line.sequence,
                'product_id': line.product_id.id,
                'price_unit': line.price_unit,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom.id,
                'date_deadline': line.date_deadline,
                }))
        return res
        
    _columns = {
        'line_ids': fields.one2many(
            'sale.delivery.partial.line.wizard', 'wizard_id', 'Wizard'), 
        }
    
    _defaults = {
        'line_ids': lambda s, cr, uid, ctx: s._load_default_line_ids(
            cr, uid, ctx)
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


