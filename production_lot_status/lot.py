# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
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
import openerp.netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare,
    )
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class stock_production_lot_accounting(orm.Model):
    ''' Add extra field for manage status of lot from accounting
    '''
    _inherit = 'stock.production.lot'
    
    _columns = {
        'package_id': fields.many2one('product.ul', 'Package', 
            help='Package used for package (for this lot)'),
        # TODO remove:    
        'stock_available_accounting': fields.float('Stock availability', digits=(16, 2)),    
        'accounting_ref': fields.char('Accounting ref', size=12, 
            help="ID lot in account program"),
        'anomaly': fields.boolean('Anomaly', required=False),    
        }    

class product_product_lot_accounting(orm.Model):
    ''' Add extra field for manage status of product / lot from accounting
    '''
    _inherit = 'product.product'
    
    _columns = {
        'accounting_lot_ids': fields.one2many('stock.production.lot', 
            'product_id', 'Lots status'),
        'package_ref': fields.char('Package ref', size=12,
            help="Reference for import package, used to find product"),    
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
