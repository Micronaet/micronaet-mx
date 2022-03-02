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
    """ Document that will be attached to order
    """
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
    """ Document mandatory attached to order
    """
    _name = 'sale.order.docs.order'
    _description = 'Document for order'
    _rec_name = 'order_id'
    _order = 'sequence,docs_id'

    _columns = {
        'sequence': fields.integer('Seq.'),
        'order_id': fields.many2one('sale.order', 'Ordine'),
        'docs_id': fields.many2one('sale.order.docs', 'Documento'),
        'mandatory': fields.boolean('Obbligatori per ordine'),
        'note': fields.text('Note'),
        'present': fields.boolean('Presente (fatto)'),
        }


class SaleOrderDocsPartner(osv.osv):
    """ Document mandatory attached to order
    """
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
    """ Sale order documents
    """
    _inherit = 'sale.order'

    # -------------
    # Button event:
    # -------------
    # Utility for button:
    def load_only_new_from_proxy(self, cr, uid, ids, mode, context=None):
        """ Load only record not present in order, list was passed (partner or
            all element)
            mode: partner or document (origin of list to load)
        """
        # Pool used:
        docs_pool = self.pool.get('sale.order.docs')
        order_pool = self.pool.get('sale.order.docs.order')
        partner_pool = self.pool.get('sale.order.docs.partner')

        # Load current list of docs:
        current_record = self.browse(cr, uid, ids, context=context)[0]
        current_docs = [
            item.docs_id.id for item in current_record.order_docs_ids]

        # Load origin list:
        if mode == 'partner':
            if not current_record.partner_id:
                return True  # todo alert or delete all?
            partner_id = current_record.partner_id.id
            partner_ids = partner_pool.search(cr, uid, [
                ('partner_id', '=', partner_id)], context=context)
            item_proxy = partner_pool.browse(
                cr, uid, partner_ids, context=context)
        else: # 'document'
            docs_ids = docs_pool.search(cr, uid, [], context=context)
            item_proxy = docs_pool.browse(cr, uid, docs_ids, context=context)

        # Create only new elements:
        for item in item_proxy:
            # 2 different key depend on mode:
            if mode == 'partner':
                key_id = item.docs_id.id
            else: #'document'
                key_id = item.id
            if key_id not in current_docs:
                order_pool.create(cr, uid, {
                    'order_id': ids[0],
                    'docs_id': key_id,
                    'mandatory': item.mandatory,
                    'note': item.note,
                    }, context=context)
        return True

    def dummy_button(self, cr, uid, ids, context=None):
        """ Dummy button do nothing
        """
        return True

    def load_from_partner(self, cr, uid, ids, context=None):
        """ Load list from anagraphic
        """
        return self.load_only_new_from_proxy(
            cr, uid, ids, 'partner', context=context)

    def load_from_list(self, cr, uid, ids, context=None):
        """ Load list from anagraphic
        """
        return self.load_only_new_from_proxy(
            cr, uid, ids, 'document', context=context)

    def _get_extra_doc_status(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = {}
            res[item.id]['extra_doc_error'] = False
            total = [0, 0, 0, 0] # done / mandatory, done / not mandatory
            for line in item.order_docs_ids:
                if line.mandatory:
                    total[1] += 1
                    if line.present:
                        total[0] += 1
                else:
                    if line.present:
                        total[2] += 1
                    total[3] += 1
            if total[0] != total[1] or total[2] != total[3]:
                res[item.id]['extra_doc_error'] = True
            if any(total):
                res[item.id][
                    'extra_doc_status'] = '%s/%s(mand) %s/%s' % (
                        total[0], total[1], total[2], total[3])
            else:
                res[item.id]['extra_doc_status'] = False
        return res

    _columns = {
        'order_docs_ids': fields.one2many('sale.order.docs.order', 'order_id',
            'Mandatory document'),
        'extra_doc_status': fields.function(
            _get_extra_doc_status, method=True,
            type='char', size='40', string='Docs',
            store=False, multi=True),
        'extra_doc_error': fields.function(
            _get_extra_doc_status, method=True,
            type='boolean', string='Docs error',
            store=False, multi=True),
        }


class ResPartner(osv.osv):
    """ Document that will be attached to order
    """
    _inherit = 'res.partner'


    # ------------------------
    # Override onchange event:
    # ------------------------
    """def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        ''' Override event for load docs list from partner
        '''
        if partner_id:
            
        partner_pool = self.pool.get('sale.order.docs.partner')

        res = super(ClassName, self).write(
            cr, user, ids, vals, context=context)
        
        retrun True"""

    # -------------
    # Button event:
    # -------------
    def load_from_list(self, cr, uid, ids, context=None):
        """ Load list from record (quite same to order but use different
            object so keep this quite similar duplicate
        """
        docs_pool = self.pool.get('sale.order.docs')
        partner_pool = self.pool.get('sale.order.docs.partner')

        current_docs = [
            item.docs_id.id for item in self.browse(
                cr, uid, ids, context=context)[0].order_docs_ids]
        docs_ids = docs_pool.search(cr, uid, [], context=context)
        for item in docs_pool.browse(cr, uid, docs_ids, context=context):
            if item.id not in current_docs:
                partner_pool.create(cr, uid, {
                    'partner_id': ids[0],
                    'docs_id': item.id,
                    'mandatory': item.mandatory,
                    'note': item.note,
                    }, context=context)
        return True

    _columns = {
        'order_docs_ids': fields.one2many(
            'sale.order.docs.partner', 'partner_id', 'Mandatory document'),
        }
