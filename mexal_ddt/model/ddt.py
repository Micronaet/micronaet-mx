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

#class StockPicking(orm.Model):
#    _inherit = 'stock.picking.out'
#    
#    _columns = {
#        'mx_move_lines': fields.one2many('mx.stock.move', 'picking_id', 
#            'Details'),
#        }

    #def draft_force_assign(self, cr, uid, ids, *args):
    #    """ Confirms picking directly from draft state.
    #        @return: True
    #    """
    #    wf_service = netsvc.LocalService("workflow")
    #    for pick in self.browse(cr, uid, ids):
    #        if not pick.mx_move_lines:
    #            raise osv.except_osv(_('Error!'),_('You cannot process picking without stock moves.'))
    #        wf_service.trg_validate(uid, 'stock.picking', pick.id,
    #            'button_confirm', cr)
    #    return True

#class AccountInvoiceTax(orm.Model):
#    _inherit = "account.invoice.tax"
#
#    _columns = {
#         # extra fields
#         }

#class mx_ddt_carriage_condition(orm.Model):
#    _inherit = ""

#    _columns = {
 #        # extra fields
  #       }
                
#class mx_ddt_description_goods(orm.Model):
 #   _inherit = ""

  #  _columns = {
         # extra fields
#         }

#class mx_ddt_payment(orm.Model):
 #   _inherit = ""

  #  _columns = {
         # extra fields
   #      }

#class mx_ddt_reason_transport(orm.Model):
 #   _inherit = ""

  #  _columns = {
         # extra fields
   #      }

#class mx_ddt_transport(orm.Model):
 #   _inherit = "mx.ddt.transport"

  #  _columns = {
         # extra fields
   #      }

# TODO moved in a module???
#class mx_ddt_vector(orm.Model):
 #   _inherit = "mx.ddt.vector"

  #  _columns = {
         # extra fields
   #      }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
