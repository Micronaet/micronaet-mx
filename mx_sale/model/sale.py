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

#class SaleOrder(orm.Model):
#    ''' Extra field for order
#    '''
#    
#    _inherit = 'sale.order'
#    
#    _columns = {
#        'pick_ids': fields.one2many('stock.pickin.out', 'sale_id', 
#            'Picking'),
#        }
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
            res[line] = 0.0
            move_ids = move_pool.search(cr, uid, [
                ('sale_line_id', '=', line)], context=context)
            for line in move_pool.search(cr, uid, move_ids, context=context):
                if line.picking_id.ddt_number: # was marked as DDT
                    # TODO check UOM!!! for 
                    res[line] += line.product_qty
        return res
        
    _columns = {
        'delivered_qty': fields.function(
            _function_get_delivered, method=True, type='float', 
            string='Delivered', store=False),
                        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
