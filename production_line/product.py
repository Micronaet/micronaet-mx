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
import openerp.netsvc as netsvc
import logging
from openerp import tools
from openerp.osv import osv, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from utility import no_establishment_group


_logger = logging.getLogger(__name__)

class product_ul_extra(osv.osv):
    ''' Extra fields for product.product object
    '''    
    _name = "product.ul"
    _inherit = "product.ul"
    
    _columns = {
        'code': fields.char('Code', size=10, required=False, readonly=False),
        'linked_product_id': fields.many2one('product.product', 'Product linked', required=False, help="Used for unload package product after lavoration"),
    }

class product_product_extra(osv.osv):
    ''' Extra fields for product.product object
    '''
    _inherit = "product.product"

    # -------------
    # Override ORM:
    # -------------
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False):
        """
        Return a view and fields for current model. where view will be depends on {view_type}.
        @param cr: cursor to database
        @param uid: id of current user
        @param view_id: list of fields, which required to read signatures
        @param view_type: defines a view type. it can be one of (form, tree, graph, calender, gantt, search, mdx)
        @param context: context arguments, like lang, time zone
        @param toolbar: contains a list of reports, wizards, and links related to current model
        
        @return: returns a dict that contains definition for fields, views, and toolbars
        """        
        if view_type == 'form' and no_establishment_group(self, cr, uid, context=context):
            toolbar = False
        return super(product_product_extra, self).fields_view_get(
            cr, uid, view_id, view_type, context=context, toolbar=toolbar)

    # Fields functions:
    def _function_linked_accounting_qty(self, cr, uid, ids, field, args, context=None):
        """ Calculate total of sale order line for used for accounting store
        """ 
        res = dict.fromkeys(ids, 0)
        sol_pool = self.pool.get('sale.order.line')
        sol_ids = sol_pool.search(cr, uid, [('product_id','in',ids),('use_accounting_qty','=',True)], context=context)
        for line in sol_pool.browse(cr, uid, sol_ids, context=context):
            try: 
                res[line.product_id.id] += line.product_uom_qty or 0.0
            except:
                pass # no error!
        return res        
        
    _columns = {
        # TODO remove
        'accounting_qty': fields.float('Account quantity', digits=(16, 3)),
        
        'linked_accounting_qty': fields.function(_function_linked_accounting_qty, method=True, type='float', string='OC qty linked to store', store=False, multi=False),
                
        # TODO remove:        
        'minimum_qty': fields.float('Minimum alert quantity', digits=(16, 3)),
        'maximum_qty': fields.float('Maximum alert quantity', digits=(16, 3)),
        
        'not_in_status': fields.boolean('Not in status', help='If checked in webkit report of status doesn\'t appear'), 
        #'to_produce': fields.boolean('To produce', help='If checked this product appear on list of os lines during creation of production orders'), 
        
        'is_pallet': fields.boolean('Is a pallet', help='The product is a pallet '), 
        'pallet_max_weight': fields.float('Pallet weight', digits=(16, 3), help='Max weight of the load on this pallet'),
        }

    _defaults = {
        'not_in_status': lambda *a: False, 
        'is_pallet': lambda *a: False,         
        }          

# ID function:
def get_partner_id(self, cr, uid, ref, context=None):
    ''' Get OpenERP ID for res.partner with passed accounting reference
    '''
    partner_id=self.pool.get("res.partner").search(cr, uid, ["|","|",('mexal_c','=',ref),('mexal_d','=',ref),('mexal_s','=',ref)], context=context)
    return partner_id[0] if partner_id else False

def browse_partner_id(self, cr, uid, item_id, context=None):
    ''' Return browse obj for partner id
    '''
    browse_ids = self.pool.get('res.partner').browse(cr, uid, [item_id], context=context)
    return browse_ids[0] if browse_ids else False

def browse_partner_ref(self, cr, uid, ref, context=None):
    ''' Get OpenERP ID for res.partner with passed accounting reference
    '''
    partner_id = self.pool.get("res.partner").search(cr, uid, [
        "|", "|", 
        ('mexal_c','=',ref), 
        ('mexal_d','=',ref), 
        ('mexal_s','=',ref), ], context=context)
    return self.pool.get('res.partner').browse(
        cr, uid, partner_id[0], context=context) if partner_id else False

def get_product_id(self, cr, uid, ref, context=None):
    ''' Get OpenERP ID for product.product with passed accounting reference
    '''
    item_id = self.pool.get('product.product').search(cr, uid, [
        ('default_code', '=', ref)], context=context)
    return item_id[0] if item_id else False

def browse_product_id(self, cr, uid, item_id, context=None):
    ''' Return browse obj for product id
    '''
    browse_ids = self.pool.get('product.product').browse(
        cr, uid, [item_id], context=context)
    return browse_ids[0] if browse_ids else False

def browse_product_ref(self, cr, uid, ref, context=None):
    ''' Return browse obj for product ref
        Create a minimal product with code ref for not jump oc line creation
        (after normal sync of product will update all the fields not present
    '''
    item_id = self.pool.get('product.product').search(cr, uid, [
        ('default_code', '=', ref)], context=context)
    if not item_id:
       try:
           uom_id = self.pool.get('product.uom').search(cr, uid, [
               ('name', '=', 'kg')],context=context)
           uom_id = uom_id[0] if uom_id else False
           item_id=self.pool.get('product.product').create(cr,uid,{
               'name': ref,
               'name_template': ref,
               'mexal_id': ref,
               'default_code': ref,
               'sale_ok': True,
               'type': 'consu',
               'standard_price': 0.0,
               'list_price': 0.0,
               'description_sale': ref, # preserve original name (not code + name)
               'description': ref,
               'uos_id': uom_id,
               'uom_id': uom_id,
               'uom_po_id': uom_id,
               'supply_method': 'produce',
           }, context=context)
       except:
           return False # error creating product
    else:
        item_id=item_id[0]  # first
    return self.pool.get('product.product').browse(cr, uid, item_id, context=context)

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
