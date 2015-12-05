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

class SaleOrderDocs(osv.osv):    
    ''' Document that will be attached to order
    '''
    _name = 'sale.order.docs'
    _description = 'Mandatory document'
    _order = 'sequence,name'
    
    _columns = {
        'name': fields.char('Document name', size=100, required=True),
        'sequence': fields.integer('Seq.'), 
        'mandatory': fields.boolean('Mandatory', help='Always mandatory'),
        'note': fields.text('Note'),
        }

class SaleOrderDocsOrder(osv.osv):    
    ''' Document mandatory attached to order
    '''
    _name = 'sale.order.docs.order'
    _description = 'Document for order'
    _rec_name = 'order_id'
    _order = 'sequence,docs_id'
    
    _columns = {
        'sequence': fields.integer('Seq.'), 
        'order_id': fields.many2one('sale.order', 'Order'),
        'docs_id': fields.many2one('sale.order.docs', 'Document'),
        'mandatory': fields.boolean('Mandatory for order'),
        'note': fields.text('Note'),
        }

class SaleOrderDocsPartner(osv.osv):    
    ''' Document mandatory attached to order
    '''
    _name = 'sale.order.docs.partner'
    _description = 'Document for partner'
    _rec_name = 'partner_id'
    _order = 'sequence,docs_id'
    
    _columns = {
        'sequence': fields.integer('Seq.'), 
        'partner_id': fields.many2one('res.partner', 'Order'),
        'docs_id': fields.many2one('sale.order.docs', 'Document'),
        'mandatory': fields.boolean('Mandatory for customer'),
        'note': fields.text('Note'),
        }

class SaleOder(osv.osv):    
    ''' Sale order documents
    '''    
    _inherit = 'sale.order'
    
    # -------------
    # Button event:
    # -------------
    # Utility for button:
    def load_only_new_from_proxy(self, cr, uid, ids, mode, context=None):
        ''' Load only record not present in order, list was passed (partner or
            all element)
            mode: 
                partner > in sale order load partner list
                document > in sale order load document list
                list > in partner load document list
        '''
        # Pool used:
        docs_pool = self.pool.get('sale.order.docs')        
        order_pool = self.pool.get('sale.order.docs.order')        
        partner_pool = self.pool.get('sale.order.docs.partner')
        
        # Load current list of docs:
        current_record = self.browse(cr, uid, ids, context=context)[0]        
        partner_id = current_record.partner_id.id
        if mode == 'list': # different in partner:
            partner_docs = partner_pool.search(cr, uid, [
                ('id', '=', partner_id)], context=context)
            current_docs = [item.docs_id.id for item in partner_pool.browse(
                cr, uid, partner_docs, context=context)]
        elif: # document or partner   
            current_docs = [item.docs_id.id for item in \
                current_record.order_docs_ids]
            
        # Load origin list:    
        key_field = 'order_id'
        target_pool = order_pool    
        if mode == 'partner':
            if not current_record.partner_id:
                return True # TODO alert or delete all?
            partner_ids = partner_pool.search(cr, uid, [
                ('partner_id', '=', partner_id)], context=context)
            item_proxy = partner_pool.browse(
                cr, uid, partner_ids, context=context)    
        else: # 'document' and 'list' cases:
            if mode == 'list': 
                key_field = 'partner_id' # link to partner (no order)          
                target_pool = partner_pool    
            docs_ids = docs_pool.search(cr, uid, [], context=context)
            item_proxy = docs_pool.browse(cr, uid, docs_ids, context=context)
        
        # Create only new elements:    
        for item in item_proxy:
            # 2 different key depend on mode:            
            if mode == 'partner':
                key_id = item.docs_id.id
            else: #'document', 'list'
                key_id = item.id
            if key_id not in current_docs:
                target_pool.create(cr, uid, {
                    key_field: ids[0],
                    'docs_id': key_id,
                    'mandatory': item.mandatory,
                    'note': item.note,
                    }, context=context)
        return True
        
    def load_from_partner(self, cr, uid, ids, context=None):
        ''' Load list from anagraphic
        '''
        return self.load_only_new_from_proxy(
            cr, uid, ids, 'partner', context=context)

    def load_from_list(self, cr, uid, ids, context=None):
        ''' Load list from anagraphic
        '''
        return self.load_only_new_from_proxy(
            cr, uid, ids, 'document', context=context)
        
    _columns = {
        'order_docs_ids': fields.one2many('sale.order.docs.order', 'order_id',
            'Mandatory document'),
        }


class ResPartner(osv.osv):    
    ''' Document that will be attached to order
    '''
    _inherit = 'res.partner'

    # Button event:
    def load_from_list(self, cr, uid, ids, context=None):
        ''' Load list from anagraphic
        '''
        return self.pool.get('sale.order').load_only_new_from_proxy(
            cr, uid, ids, 'list', context=context)
    
    _columns = {
        'order_docs_ids': fields.one2many('sale.order.docs.partner', 'partner_id',
            'Mandatory document'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
