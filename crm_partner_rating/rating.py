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

class ResPartner(orm.Model):
    """ Model name: ResPartner
    """
    
    _inherit = 'res.partner'
    
    _columns = {
        'rating_ids': fields.one2many(
            'res.partner.rating', 'partner_id', 
            'Rating'),     
        }
    
class ResPartnerRating(orm.Model):
    """ Model name: ClassNameCamelCase
    """    
    _name = 'res.partner.rating'
    _description = 'Partner rating'
    _rec_name = 'date'
    _order = 'date'
    
    _columns = {
        'date': fields.date('Date', required=True),
        'partner_id': fields.many2one('res.partner', 'Partner'), 
        'contact': fields.char('Contact', size=64),
        'product_note': fields.text('Product'),
        'service_note': fields.text('Service'),
        'satisfaction_note': fields.text('Satisfaction'),
        'observations_note': fields.text('Observations'),
        'signature':fields.boolean('Signature'),
        }
    
    _defaults = {
        'date': lambda *a: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
