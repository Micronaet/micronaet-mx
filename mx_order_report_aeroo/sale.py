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

class SaleOrder(orm.Model):
    """ Model name: SaleOrder
    """
    
    _inherit = 'sale.order'
    
    # ------------------
    # Override function:
    # ------------------
    def print_quotation(self, cr, uid, ids, context=None):
        ''' This function prints the sales order and mark it as sent
            so that we can see more easily the next step of the workflow
        '''
        assert len(ids) == 1, \
            'This option should only be used for a single id at a time'

        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(
            uid, 'sale.order', ids[0], 'quotation_sent', cr)
        
        datas = {
            'model': 'sale.order',
            'ids': ids,
            'form': self.read(cr, uid, ids[0], context=context),
            }
        return {
            'type': 'ir.actions.report.xml', 
            'report_name': 'custom_mx_order_report', 
            'datas': datas, 
            'nodestroy': True,
            }
    _columns = {
        'quotation_mode': fields.selection([
            ('with', 'With code'),
            ('without', 'Without code'),
            ], 'Quotation mode', required=True)
        }

    _defaults = {    
        # Default value:
        'quotation_mode': lambda *x: 'with',
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
