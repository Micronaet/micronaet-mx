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


discount_type = [
    ('integrated', 'Integrate'),
    ('inline', 'Inline'),
    ('row', 'Different row'),
    ]
    
class ResPartner(orm.Model):
    ''' Extra elemtent for manage discount
    '''    
    _inherit = 'res.partner'

    def onchange_discount(self, cr, uid, ids, discount_scale, discount, 
            mode='scale', context=None):
        ''' Update discount depend on scale (or reset scale)
        '''
        res = {'value': {}}
        try:
            if mode == 'scale':
                scale = discount_scale.split('+')
                discount_scale_cleaned = ''      
                rate = 100.0
                for i in scale:
                    i = float(i.strip().replace('%', '').replace(',', '.'))
                    rate -= rate * i / 100.0                
                    discount_scale_cleaned += "%s%5.2f%s " % (
                        '+' if discount_scale_cleaned else '', i, '%')
                res['value']['discount'] = 100.0 - rate
                res['value']['discount_scale'] = discount_scale_cleaned

            else: # 'discount':
                pass #res['value']['discount_scale'] = False
        except:
            res['warning'] = {
                'title': _('Discount error'), 
                'message': _('Scale value not correct!'),
                }
        return res        
        
    _columns = {
        'discount_type': fields.selection(discount_type, 'Discount type'),
        'discount_scale': fields.char('Discount scale', size=35),
        'discount': fields.float('Discount', digits=(
            16, 2), help='Automated calculate if scale is indicated'), 
        }
    
    _defaults = {
        'discount_type': lambda *x: 'integrated',
        }    

class SaleOrderLine(orm.Model):
    ''' Add agent commission
    '''    
    _inherit = 'sale.order.line'

    _columns = {
        'discount_type': fields.selection(discount_type, 'Discount type'),
        'discount_scale': fields.char('Discount scale', size=15),
        }
