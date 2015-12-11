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
    ''' Add alternative method for picking creation
    '''
    _inherit = 'sale.order'

    # -------------------------------------------------------------------------
    #                      Alternative method (not overrided)
    # -------------------------------------------------------------------------    
    def _create_pickings_from_wizard(self, cr, uid, order, order_line_ids, 
            context=None):            
        """ Alternative method of _create_pickings_and_procurements
            order: browse obj as order source
            order_line: dict of order line and qty to pick out
        """
        context = context or {}
        
        # Pool used:        
        line_pool = self.pool.get('sale.order.line')
        move_pool = self.pool.get('stock.move')
        picking_pool = self.pool.get('stock.picking')

        # Browse obj used:
        order_line = line_pool.browse(cr, uid, order_line_ids.keys(), 
            context=context)
        
        # ---------------------------------------------------------------------
        # Picking creation:
        # ---------------------------------------------------------------------
        # Get normal data from original function:
        picking_data = self._prepare_order_picking(
            cr, uid, order, context=context)

        # Add extra fields to picking:
        picking_data['date'] = context.get(
            'force_date_deadline', False) or datetime.now().strftime(
                DEFAULT_SERVER_DATE_FORMAT)
        
        # Add dependency for this fields: TODO vector and others needed!
        extra_fields = ('transportation_reason_id', 
                'goods_description_id', 'carriage_condition_id')
        for field in extra_fields:
            picking_data[field] = order.__getattr__(field).id
        
        # Create record        
        picking_id = picking_pool.create(cr, uid, picking_data, 
            context=context)
        
        # ---------------------------------------------------------------------
        #                    TODO Split depend on deadline date
        # ---------------------------------------------------------------------
        for line in order_line:
            #if line.state == 'done':
            #    continue

            if line.product_id:
                if line.product_id.type in ('product', 'consu'): # not service
                    move_data = self._prepare_order_line_move(
                        cr, uid, order, line, picking_id, 
                        picking_data['date'],
                        context=context)
                    # Force qty:
                    product_uom_qty = order_line_ids[line.id]                        
                    move_id = move_pool.create(
                        cr, uid, move_data, context=context)
                else:
                    # a service has no stock move
                    move_id = False

        wf_service = netsvc.LocalService("workflow")
        if picking_id:
            wf_service.trg_validate(
                uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
