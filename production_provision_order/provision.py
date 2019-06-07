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

class PurchaseOrderProvision(orm.Model):
    """ Model name: PurchaseOrderProvision
    """
    
    _name = 'purchase.order.provision'
    _description = 'Provision order'
    _rec_name = 'name'
    _order = 'name'
    
    # Scheduled operation:
    def scheduled_generate_provision_order(self, cr, uid, days=31, 
            context=None):    
        ''' Generate report to test after the stock level
            Add extra parameter?        
        '''
        # Pool used:
        mrp_pool = self.pool.get('mrp.production')
        wiz_pool = self.pool.get('product.status.wizard')
        line_pool = self.pool.get('purchase.order.provision.line')
                
        # ---------------------------------------------------------------------
        # Create wizard record:
        # ---------------------------------------------------------------------
        wiz_id = wiz_pool.create(cr, uid, { 
            'days': days,
            'with_medium': False,
            'month_window': 0,
            'with_order_detail': False,
            #'row_mode': '',
            #'fake_ids': 
            }, context=context)
        
        # ---------------------------------------------------------------------
        # Generate report:    
        # ---------------------------------------------------------------------
        wiz_pool.export_excel(cr, uid, [wiz_id], context=context)    
        
        # ---------------------------------------------------------------------
        # Get collected data:
        # ---------------------------------------------------------------------
        table = mrp_pool._get_table()
        rows = mrp_pool._get_rows()
        
        sequence = 0
        purchase_id = False
        for row in rows:
            # Only raw material
            if row[0] != 'M':
                continue
            
            product = row[2]
            product_id = row[1]
            detail = table[product_id]
            
            # Get stock level management:
            day_min_level = product.day_min_level
            day_max_level = product.day_max_level
            min_stock_level = product.min_stock_level
            max_stock_level = product.max_stock_level
            
            if day_min_level > days:
                _logger.error('Product %s stock level %s > %s' % (
                    product.default_code,
                    day_min_level,
                    days,
                    ))
                continue
                
            urgent = False
            status_day_min = detail[day_min_level]    
            # Under stock min level:
            if status_day_min < min_stock_level:
                provision_qty = max_stock_level - status_day_min

            # Negative     
            if status_day_min < 0:
                urgent = True
            
            # Create header if not present:
            if not purchase_id:
                now = datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT)
                purchase_id = self.create(cr, uid, {
                    'name': 'Ordine previsionale %s' % now, # TODO number?
                    'date': now,                    
                    }, context=context)
            
            # -----------------------------------------------------------------
            # Line:    
            # -----------------------------------------------------------------
            sequence += 10
            line_pool.create(cr, uid, {
                'sequence': sequence,
                'urgent': urgent,
                'purchase_id': purchase_id,
                'product_id': product_id, 
                'provision_qty': provision_qty,
                'real_qty': provision_qty,
                'supplier_id': False, # TODO!!!
                'list_price': product.standard_price, # TODO quotation for sup.
                # 'state'
                }, context=context)               
        
        # If launched via button return the view:        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Provision order'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_id': purchase_id,
            'res_model': 'purchase.order.provision',
            'view_id': False,
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'date': fields.date('Date', required=True),
        # TODO Add provision order managed with this!!!
        }

class PurchaseOrderProvisionLine(orm.Model):
    """ Model name: PurchaseOrderProvision
    """
    
    _name = 'purchase.order.provision.line'
    _description = 'Provision order line'
    _rec_name = 'product_id'
    _order = 'sequence,product_id'
    
        
    _columns = {
        'sequence': fields.integer('Seq.'),
        'urgent': fields.boolean('Urgent', 
            help='Was negative in stock level period'),
        'purchase_id': fields.many2one('purchase.order.provision', 'Order'),
        'product_id': fields.many2one('product.product', 'Product'),
        'provision_qty': fields.float('Provision qty', digits=(16, 2)),
        'real_qty': fields.float('Real qty', digits=(16, 2)),
        'supplier_id': fields.many2one('res.partner', 'Supplier'),
        'list_price': fields.float('List price', digits=(16, 2)),
        # TODO Add provision order managed with this!!!
        'state': fields.selection([
            ('draft', 'Draft'),
            ('done', 'Done'),
            ], 'State', required=True),
        }
    _defaults = {
        # Default value:
        'state': lambda *x: 'draft',
        }    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
