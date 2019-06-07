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


class ResPartner(orm.Model):
    """ Model name: Res Partner
    """
    
    _inherit = 'res.partner'

    def print_partner_purchase(self, cr, uid, ids, context=None):
        ''' Print purchase report for partner selected
        '''
        if context is None:
            context = {}
        purchase_id = context.get('purchase_id', False)
        
        # TODO Print report for this partner with purchase_id selected
        return True        

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'

    def save_dummy(self, cr, uid, ids, context=None):
        ''' Dummy button for save record
        '''
        return True        
        
class PurchaseOrderProvision(orm.Model):
    """ Model name: PurchaseOrderProvision
    """
    
    _name = 'purchase.order.provision'
    _description = 'Provision order'
    _rec_name = 'name'
    _order = 'name desc'
    
    def dummy(self, cr, uid, ids, context=None):
        ''' Dummy button
        '''
        return True
        
    def check_negative_compensed(self, product, detail):
        ''' Check negative in lead time period
        '''
        day_leadtime = product.day_leadtime
        min_stock_level = product.min_stock_level
        mode = False

        for day in range(0, day_leadtime):
            check = sum(detail[:(day + 1)])
            if check < min_stock_level:
                mode = 'min'
            elif check < 0:
                mode = 'negative'
                break
        return mode        
        
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
        negative_pool = self.pool.get('purchase.order.provision.negative')
        product_pool = self.pool.get('product.product')
        previsional_pool = self.pool.get('mrp.production.previsional')
                
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
        
        wizard = wiz_pool.browse(cr, uid, wiz_id, context=context)
        fake_detail = ''

        fake_ids = []
        for fake in wizard.fake_ids:
            fake_ids.append(fake.id)
            fake_detail += '%s. Produzione ipotetica %s Q. %s\n' % (
                fake.production_date,
                fake.product_id.default_code or fake.product_id.name,
                fake.qty,
                )
        if fake_ids:         
            _logger.info('Mark as used all previsional order')
            previsional_pool.wkf_draft_2_used(
                cr, uid, fake_ids, context=context)       
        
        # ---------------------------------------------------------------------
        # Generate report:    
        # ---------------------------------------------------------------------
        _logger.info('Extract data simulated days: %s' % days)
        wiz_pool.export_excel(cr, uid, [wiz_id], context=context)    
        
        # ---------------------------------------------------------------------
        # Get collected data:
        # ---------------------------------------------------------------------
        table = mrp_pool._get_table()
        rows = mrp_pool._get_rows()
        
        _logger.info('Generate purchase data')
        sequence = 0
        purchase_id = False
        now = datetime.now()
        status_mask = _(
            '''Leadtime %s, m(x): %s,
               Day min: %s (q. %s), Day max: %s (q. %s)
               Q. at leadtime period: %s
               Max %s - Lead q. %s = %s
               ''')

        # TODO manage negative in period! (and under level)
        for row in rows:
            # Only raw material
            if row[0] != 'M':
                continue
            
            product = row[2]
            product_id = row[1]
            detail = table[product_id]

            # Get stock level management:
            day_leadtime = product.day_leadtime
            day_min_level = product.day_min_level
            day_max_level = product.day_max_level
            min_stock_level = product.min_stock_level
            max_stock_level = product.max_stock_level
            medium_stock_qty = product.medium_stock_qty
            
            if day_min_level > days:
                _logger.error('Product %s stock level %s > %s' % (
                    product.default_code,
                    day_min_level,
                    days,
                    ))
                continue

            # Purchase data:
            now_text = now.strftime(DEFAULT_SERVER_DATE_FORMAT)
            purchase_header = {
                    'name': _('Ordine approvvigionamento %s') % now, # TODO number?
                    'date': now_text,     
                    'fake_detail': fake_detail,               
                    }

            status_leadtime = sum(detail[:(day_leadtime + 1)])

            # -----------------------------------------------------------------
            # Under stock min level qty:
            # -----------------------------------------------------------------
            if status_leadtime < min_stock_level:
                provision_qty = max_stock_level - status_leadtime
            else:
                # Check if the element bo in negative state:
                negative_mode = self.check_negative_compensed(product, detail)
                if negative_mode:
                    if not purchase_id:
                        purchase_id = self.create(
                            cr, uid, purchase_header, context=context)
                    negative_pool.create(cr, uid, {
                        'purchase_id': purchase_id,
                        'product_id': product_id, 
                        'mode': negative_mode,
                        }                    )
                continue # no provision needed    

            # Negative means urgent:
            urgent = status_leadtime < 0
            
            # Create header if not present:
            if not purchase_id:
                purchase_id = self.create(
                    cr, uid, purchase_header, context=context)
            
            # -----------------------------------------------------------------
            # Line:    
            # -----------------------------------------------------------------
            note = status_mask % (
                day_leadtime,
                medium_stock_qty,
                
                day_min_level,
                min_stock_level,
                
                day_max_level,
                max_stock_level,
                
                status_leadtime,
                
                # Operation:
                max_stock_level,
                status_leadtime,
                provision_qty,
                )

            sequence += 10
            line_pool.create(cr, uid, {
                'sequence': sequence,
                'urgent': urgent,
                'purchase_id': purchase_id,
                'product_id': product_id, 
                'provision_qty': provision_qty,
                'real_qty': product_pool.round_interger_order(
                    provision_qty,
                    approx=product.approx_integer, 
                    mode=product.approx_mode),
                'supplier_id': product.first_supplier_id.id,
                'list_price': product.standard_price, # TODO quotation for sup.
                'deadline': (now + relativedelta(day_leadtime)).strftime(
                    DEFAULT_SERVER_DATE_FORMAT),
                'note': note,    
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

    def _get_supplier_list(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''        
        res = {}
        if len(ids) > 1:
            return res
        
        item_id = ids[0]
        res[item_id] = []
        for line in self.browse(cr, uid, ids, context=context)[0].line_ids:
            partner_id = line.supplier_id.id
            if partner_id and partner_id not in res[item_id]:
                res[item_id].append(partner_id)
        return res

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'date': fields.date('Date', required=True),
        'fake_detail': fields.text('Fake detail'),
        'supplier_ids': fields.function(
            _get_supplier_list, method=True, relation='res.partner',
            type='many2many', string='Supplier'), 
                        
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

class PurchaseOrderProvisionNegative(orm.Model):
    """ Model name: PurchaseOrderNegative
    """
    
    _name = 'purchase.order.provision.negative'
    _description = 'Provision negative product'
    _rec_name = 'product_id'
    _order = 'product_id'
    
    # Button
    def generate_purchase_row(self, cr, uid, ids, context=None):
        ''' Create line for purchase
        '''
        line_pool = self.pool.get('purchase.order.provision.line')

        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        product = current_proxy.product_id
        
        now = datetime.now()
        line_id = line_pool.create(cr, uid, {
            'sequence': 1000,
            'urgent': True,
            'purchase_id': current_proxy.purchase_id.id,
            'product_id': product.id, 
            'provision_qty': 0.0,
            'real_qty': 0.0,
            'supplier_id': product.first_supplier_id.id,
            'list_price': product.standard_price, # TODO quotation for sup.
            'deadline': (now + relativedelta(product.day_leadtime)).strftime(
                DEFAULT_SERVER_DATE_FORMAT),
            'note': 'Generato dai negativi',
            }, context=context) 
        
        # Update for hide button                  
        return self.write(cr, uid, ids, {
            'line_id': line_id, 
            }, context=context)

    _columns = {
        'purchase_id': fields.many2one('purchase.order.provision', 'Order'),
        'product_id': fields.many2one('product.product', 'Product'),         
        'mode': fields.selection([
            ('negative', 'Negative'),
            ('min', 'Under min level'),
            ], 'Mode'),
        'line_id': fields.many2one(
            'purchase.order.provision.line', 'Line'),    
        }        
        
    _defaults = {
        # Default value:
        'mode': lambda *x: 'negative',
        }    

class PurchaseOrderProvisionLine(orm.Model):
    """ Model name: PurchaseOrderProvision
    """
    
    _name = 'purchase.order.provision.line'
    _description = 'Provision order line'
    _rec_name = 'product_id'
    _order = 'sequence,product_id'

    # Button event:
    def open_product_detail(self, cr, uid, ids, context=None):
        ''' Open detail for product
        '''
        if context is None:
            context = {}
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        context['open_popup'] = True
        return {
            'type': 'ir.actions.act_window',
            'name': _('Product detail'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': current_proxy.product_id.id,
            'res_model': 'product.product',
            'view_id': False,
            'views': [(False, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    _columns = {
        'sequence': fields.integer('Seq.'),
        'urgent': fields.boolean('Urgent', 
            help='Was negative in stock level period'),
        'purchase_id': fields.many2one('purchase.order.provision', 'Order'),
        'product_id': fields.many2one('product.product', 'Product'),
        'provision_qty': fields.float('Provision qty', digits=(16, 2)),
        'real_qty': fields.float('Real qty', digits=(16, 2)),
        'supplier_id': fields.many2one('res.partner', 'Supplier'),
        'deadline': fields.date('Deadline'),
        'list_price': fields.float('List price', digits=(16, 2)),
        'note': fields.text('Note'),
        # TODO Add provision order managed with this!!!
        }

class PurchaseOrderProvisionRelation(orm.Model):
    """ Model name: PurchaseOrderProvision
    """
    
    _inherit = 'purchase.order.provision'
    
    _columns = {
        'line_ids': fields.one2many(
            'purchase.order.provision.line', 'purchase_id', 'Detail'),
        'negative_ids': fields.one2many(
            'purchase.order.provision.negative', 'purchase_id', 'Negative'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
