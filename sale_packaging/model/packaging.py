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


class ProductUl(orm.Model):
    """ Add package in product ul
    """
    _inherit = 'product.ul'

    _columns = {
        'return_package': fields.boolean(
            'Package return',
            help='Will be returned'),
        }


class SaleOrderLine(orm.Model):
    """ Add package info in sale line
    """
    _inherit = 'sale.order.line'

    _columns = {
        'return_package': fields.boolean(
            'Package return',
            help='Will be returned'),
        'package_qty': fields.integer('Pack leave'),
        'package_returned_qty': fields.integer('Pack returned'),
        'return_package_ok': fields.boolean(
            'Ok returned',
            help='If checked order line is marked as returned'
                 'alse if not all element are back'),
        'package_note': fields.char('Return note', size=64),
        }

    _defaults = {
        'return_package': lambda *x: True,  # todo remove use onchange
        }
