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
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class SaleOrderMandatoryDocs(orm.Model):    
    ''' Document that will be attached to order
    '''
    _name = 'sale.order.mandatory.docs'
    _description = 'Mandatory document'
    
    _columns = {
        'sequence': fields.integer('Seq.')), 
        'name': fields.char('Document name', size=100, required=True),
        'mandatory': fields.boolean('Mandatory', help='Always mandatory'),
        'note': fields.text('Note'),
        }

class SaleOrderMandatoryOrder(orm.Model):    
    ''' Document mandatory attached to order
    '''
    _name = 'sale.order.mandatory.order'
    _description = 'Document for order'
    _rec_name = 'order_id'
    
    _columns = {
        'order_id': fields.many2one('sale.order', 'Order'),
        'docs_id': fields.many2one('sale.order.mandatory.docs', 'Document'),
        'note': fields.text('Note'),
        }

class SaleOrderMandatoryPartner(orm.Model):    
    ''' Document mandatory attached to order
    '''
    _name = 'sale.order.mandatory.partner'
    _description = 'Document for partner'
    _rec_name = 'partner_id'
    
    _columns = {
        'partner_id': fields.many2one('res.partner', 'Order'),
        'docs_id': fields.many2one('sale.order.mandatory.docs', 'Document'),
        'note': fields.text('Note'),
        }

class SaleOder(orm.Model):    
    ''' Sale order documents
    '''
    _inherit = 'sale.order'
    
    _columns = {
        fields.one2many('sale.order.mandatory.order', 'order_id',
            'Mandatory document'),
        }

class ResPartner(orm.Model):    
    ''' Document that will be attached to order
    '''
    _inherit = 'res.partner'
    
    _columns = {
        fields.one2many('sale.order.mandatory.partner', 'partner_id',
            'Mandatory document'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
