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

    _columns = {
        #'is_agent': fields.boolean('Is agent'),
        'has_commission': fields.boolean('Has commission'),
        'commission': fields.float('% Commission', digits=(8, 2), 
            help='Default value if not in product cases'), 
        'commission_ids': fields.one2many('res.partner.commission', 
            'partner_id', 'Commission'),
        }

class SaleOrderLine(orm.Model):
    ''' Add agent commission
    '''    
    _inherit = 'sale.order.line'
 
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
        
    _columns = {
        'manual': fields.boolean('Manual value', 
            help='Calculate commission value not from % but as manual'),
        'commission': fields.float('% commission', digits=(8, 2)),
        'commission_net': fields.float('Commission net', digits=(
            16, 2)), 
        'commission_value': fields.float('Commission value', digits=(
            16, 2)), 
        #'has_commission': fields.(
        #    'partner', 'has_commission'_id', 
        #    type='many2one', relation='openerp.model', 
        #    string=Label'),     
        }

