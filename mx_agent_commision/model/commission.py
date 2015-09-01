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

class ResPartnerAgentCommission(orm.Model):
    ''' Add extra object linked to agent (partner) for setup correct rate of 
        commission depend on product group
    '''
    
    _name = 'res.partner.agent.commission'
    _description = 'Agent commission'
    
    _order = 'categ_id'
    _rec_name = 'categ_id'
    
    _columns = {
        'categ_id': fields.many2one('product.category', 'Category', 
            ondelete='set null', required=True),
        'partner_id': fields.many2one('res.partner', 'Partner', 
            ondelete='cascade'),
        'rate': fields.float('Rate', digits=(8, 3), required=True), 
        'note': fields.text('Note'),
        }

class ResPartner(orm.Model):
    ''' Add commission data in partner (for agent)
    '''
    
    _inherit = 'res.partner'
    
    _columns = {
        'commission_ids': fields.one2many(
            'res.partner.agent.commission', 'partner_id', 'Commission'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
