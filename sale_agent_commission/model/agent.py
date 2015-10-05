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



class ResPartnerCommission(orm.Model):
    ''' Object for manage commissions on product sale
    '''    
    _name = 'res.partner.commission'
    _description = 'Agent commission'
    _rec_name = 'product_id'
    _order = 'sequence'
    
    _columns = {
        'sequence': fields.integer('Seq.'), 
        'partner_id': fields.many2one('res.partner', 'Agent', 
            ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product',
            ondelete='cascade'),
        'category_id': fields.many2one('product.category', 'Category',
            ondelete='cascade'), # need?    
        'commission': fields.float('% Commission', digits=(8, 2)), 
        'note': fields.text('Note'),
        }

class ResPartner(orm.Model):
    ''' Extra elemtent for manage agents
    '''    
    _inherit = 'res.partner'

    # -------------------
    # On change function:
    # -------------------

    def onchange_commission(self, cr, uid, commission, commission_net, manual,
            context=None):
        ''' Calculate commission value depend on % value and 
        '''
        res = {}
        # TODO
        
        return res

    # Override:
    """def product_id_change(self, cr, uid, ids, pricelist_id, product_id,
            product_uom_qty, product_uom, product_uos_qty, product_uos, name,
            partner_id, no1, no2, date_order, no3, fiscal_position, no4, 
            context=None):
        ''' 
        ''' 
        
        res = super(ClassName, self).write(
            cr, user, ids, vals, context=context)
        return res"""

    _columns = {
        #'is_agent': fields.boolean('Is agent'),
        'has_commission': fields.boolean('Has commission'),
        'commission': fields.float('% Commission', digits=(8, 2), 
            help='Default value if not in product cases'), 
        'commission_ids': fields.one2many('res.partner.commission', 
            'partner_id', 'Commission'),
        }
    
    _defaults = {
        'has_commission': lambda *x: True,
        }    

class SaleOrderLine(orm.Model):
    ''' Add agent commission
    '''    
    _inherit = 'sale.order.line'
 
    # -------------------
    # On change function:
    # -------------------
    """def onchange_commission(self, cr, uid, ids, commission, commission_net, 
            manual, product_uom_qty, price_unit, discount,
            context=None):
        ''' Calculate commission value depend on % value and 
        '''
        res = {'value': {}}
        if manual: # nothing
            return res
        
        if not commission: # total value nothing
            res['value']['commission_value'] = 0.0
            return res
        print discount
        if commission_net: # change base
            base = commission_net
        else:
            base = product_uom_qty * price_unit * (100.0 - discount) / 100.0
        res['value']['commission_value'] = base * commission / 100.0
        return res"""

    _columns = {
        'manual': fields.boolean('Comm. manual', 
            help='Calculate commission value not from % but as manual'),
        'commission': fields.float('% commission', digits=(8, 2)),
        'commission_net': fields.float('Commission base', digits=(
            16, 2), help='If present base price for compute commissions'), 
        'commission_value': fields.float('Commission value', digits=(
            16, 2)), 
        #'has_commission': fields.(
        #    'partner', 'has_commission'_id', 
        #    type='many2one', relation='openerp.model', 
        #    string=Label'),     
        }

