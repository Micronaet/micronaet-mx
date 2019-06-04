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
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID#, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class SaleOrderLine(osv.osv):
    """ Model name: Sale order line
    """
    
    _inherit = 'sale.order.line'
    
    _columns = {
        'ready_deadline': fields.boolean('Ready deadline', 
        help='This product has no deadline was order and keep as ready'),
        }

class ResCompany(osv.osv):
    """ Model name: Res company
    """
    
    _inherit = 'res.company'

    # TODO Parameters:    
    _columns = {
        }

class ProductProduct(osv.osv):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    def round_interger_order(self, number, approx=1, mode='over'):
        ''' Approx function for order quantity:
            Approx number to value approx (integer > 1)
            Mode = 
                'normal' (nothing is done)
                'over' (to the next approx level  exceeded)
                'under' (to the next approx level  exceeded)            
        '''
        if mode == 'over':
            extra = (approx if number % approx > 0.001 else 0)
        #elif mode == 'under':
        #    extra = (approx if number % approx > 0.001 else 0)
        else:
            extra = 0.0
        return round(number / approx , 0) * approx + extra
    
    _columns = {
        'manual_stock_level': fields.boolean('Manual stock level', 
            help='Manual has fixed q., not manual will be updated automatic'),

        # ---------------------------------------------------------------------
        # Period day for range:
        # ---------------------------------------------------------------------
        'day_leadtime': fields.integer('Lead time',
            help='Lead time period in days for receive purchase in stock '),
        'day_min_level': fields.integer('Min day time',
            help='Secure min time period in days for receive purchase in stock'
            ),
        'day_max_level': fields.integer('Max day time',
            help='Secure max time period in days for purchase'),
        'day_max_ready_level': fields.integer('Ready day time',
            help='Secure extra order for ready purchase product '
                '(for long leadtime)'),

        # ---------------------------------------------------------------------
        # Quantity fields:
        # ---------------------------------------------------------------------
        'approx_integer': fields.integer(
            'Approx (int)', help='Approx integer value, ex. 50'),
        'approx_mode': fields.selection([
            ('normal', 'Normal (nothing)'),
            ('under', 'Under approximate'),
            ('over', 'Over approximate'),
            ], 'Approx mode', 
            help='Normal nothing, Under: 145 approx 50 = 100 (not 150)'
                '105 approx 50 = 150 (not 100)',),
            
        'medium_stock_qty': fields.float('Calculated medium', digits=(16, 4),
            help='Min q. level for trigger the purchase order'),
        'min_stock_level': fields.float('Min stock level', digits=(16, 4),
            help='Min q. level for trigger the purchase order'),
        'max_stock_level': fields.float('Max stock level', digits=(16, 4),
            help='Max q. for stock level when trigger the purchase order'),
        'ready_stock_level': fields.float('Max stock level ready', 
            digits=(16, 4),
            help='Max q. for stock level when trigger the purchase order'),            
        }
        
    _defaults = {
        'approx_integer': lambda *x: 50,
        'approx_mode': lambda *x: 'over',

        'day_leadtime': lambda *x: 7,
        'day_min_level': lambda *x: 10,
        'day_max_level': lambda *x: 37,
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
