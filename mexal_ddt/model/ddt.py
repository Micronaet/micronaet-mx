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

class mx_ddt(osv.osv):
    _name = "stock.picking.out"
    _inherit = "stock.picking"
    
    _columns = {
        'mx_move_lines': fields.one2many('mx.stock.move', 'product_id', 'Mx Moves'),
        'mx_port_id': fields.many2one('mx.ddt.port', 'Port'),
        'mx_aspect_id': fields.many2one('mx.ddt.aspect', 'Aspect'),
        'mx_payment_id': fields.many2one('mx.ddt.payment', 'Payment'),
        'mx_causal_id': fields.many2one('mx.ddt.causal', 'Causal'),
        'mx_transport_id': fields.many2one('mx.ddt.transport', 'Transport'),
        'mx_vector_id': fields.many2one('mx.ddt.vector', 'Vector'),
                }
                
class mx_agent(osv.osv):
    _name = "mx.agent"
    _description = "MX Agent"

    _columns = {
        'name': fields.char('Agent', size=100, required=True),
                }

class mx_partner(osv.osv):
    _name = "mx.partner"
    _description = "MX Partner"

    _columns = {
        'name': fields.char('Partner', size=100, required=True),
                }

class mx_tax(osv.osv):
    _name = "mx.tax"
    _description = "MX Tax"

    _columns = {
        'name': fields.char('Tax', size=100, required=True),
                }

class mx_bank(osv.osv):
    _name = "mx.bank"
    _description = "MX Bank"

    _columns = {
        'name': fields.char('Bank', size=100, required=True),
                }

class mx_ledger(osv.osv):
    _name = "mx.ledger"
    _description = "MX Ledger"

    _columns = {
        'name': fields.char('Ledger', size=100, required=True),
                }

class mx_currency(osv.osv):
    _name = "mx.currency"
    _description = "MX Currency"

    _columns = {
        'name': fields.char('Currency', size=100, required=True),
                }

class mx_accounting_period(osv.osv):
    _name = "mx.accounting_period"
    _description = "MX accounting period"

    _columns = {
        'name': fields.char('Accounting period', size=100, required=True),
                }
                
class mx_uom(osv.osv):
    _name = "mx.uom"
    _description = "MX UOM"

    _columns = {
        'name': fields.char('UOM', size=100, required=True),
                }

    #=================#
    # ANAGRAFICHE DDT #
    #=================#

class mx_ddt_port(osv.osv):
    _name = "mx.ddt.port"
    _description = "DDT list port"

    _columns = {
        'name': fields.char('Port', size=80, required=True),
                }
                
class mx_ddt_aspect(osv.osv):
    _name = "mx.ddt.aspect"
    _description = "DDT aspect"

    _columns = {
        'name': fields.char('Aspect', size=80, required=True),
                }

class mx_ddt_payment(osv.osv):
    _name = "mx.ddt.payment"
    _description = "DDT payment"

    _columns = {
        'name': fields.char('Payment', size=80, required=True),
                }

class mx_ddt_causal(osv.osv):
    _name = "mx.ddt.causal"
    _description = "DDT causal"

    _columns = {
        'name': fields.char('Causal', size=80, required=True),
                }

class mx_ddt_transport(osv.osv):
    _name = "mx.ddt.transport"
    _description = "DDT transport"

    _columns = {
        'name': fields.char('Transport', size=80, required=True),
                }

class mx_ddt_vector(osv.osv):
    _name = "mx.ddt.vector"
    _description = "DDT vector"

    _columns = {
        'name': fields.char('Vector', size=80, required=True),
                }



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
