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

class SaleOrder(orm.Model):
    ''' Add alternative method for picking creation
    '''

    # -------------------------------------------------------------------------
    #                      Override original method
    # -------------------------------------------------------------------------    
    # Override for better module (currenctly modified also in sale_stock)!!    
    def _prepare_order_picking(self, cr, uid, order, context=None):
        context = context or {}
        
        # Create on date deadline if present:
        date = context.get(
            'force_date_deadline', 
            self.date_to_datetime(cr, uid, order.date_order, context))
        pick_name = self.pool.get('ir.sequence').get(
            cr, uid, 'stock.picking.out')
        return {
            'name': pick_name,
            'origin': order.name,
            'date': date,
            'type': 'out',
            'state': 'auto',
            'move_type': order.picking_policy,
            'sale_id': order.id,
            # Partner in cascade assignment:
            'partner_id': order.partner_shipping_id.id or order.address_id.id \
                or order.partner_id.id,
            'note': order.note,
            'invoice_state': (
                order.order_policy=='picking' and '2binvoiced') or 'none',
            'company_id': order.company_id.id,
        }

    def _prepare_order_line_move(self, cr, uid, order, line, picking_id, 
            date_planned, context=None):
        ''' Override for force qty in picking out (with context)
            'force_product_uom_qty': used to force value
        '''
        location_id = order.shop_id.warehouse_id.lot_stock_id.id
        output_id = order.shop_id.warehouse_id.lot_output_id.id
        product_uom_qty = context.get(
            'force_product_uom_qty', line.product_uom.id)
        # TODO used also for purchase????!!!!
        
        return {
            'name': line.name,
            'picking_id': picking_id,
            'product_id': line.product_id.id,
            'date': date_planned,
            'date_expected': date_planned,
            'product_qty': line.product_uom_qty,
            'product_uom': line.product_uom.id,
            'product_uos_qty': (line.product_uos and line.product_uos_qty) or \
                product_uom_qty,
            'product_uos': (line.product_uos and line.product_uos.id) \
                    or line.product_uom.id,
            'product_packaging': line.product_packaging.id,
            'partner_id': line.address_allotment_id.id or \
                order.partner_shipping_id.id,
            'location_id': location_id,
            'location_dest_id': output_id,
            'sale_line_id': line.id,
            'tracking_id': False,
            'state': 'draft',
            #'state': 'waiting',
            'company_id': order.company_id.id,
            'price_unit': line.product_id.standard_price or 0.0
            }
    
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
        move_pool = self.pool.get('stock.move')
        picking_pool = self.pool.get('stock.picking')

        # Browse obj used:
        order_line = self.browse(cr, uid, order_line_ids.keys(), 
            context=context)
        
        picking_id = picking_pool.create(cr, uid, self._prepare_order_picking(
            cr, uid, order, context=context))
        
        # ---------------------------------------------------------------------
        #                    TODO Split depend on deadline date
        # ---------------------------------------------------------------------
        for line in order_lines:
            if line.state == 'done':
                continue

            if line.product_id:
                if line.product_id.type in ('product', 'consu'): # not service
                    # Force q.:
                    context['force_product_uom_qty'] = 
                    move_id = move_pool.create(
                        cr, uid, self._prepare_order_line_move(
                            cr, uid, order, line, picking_id, date_planned,
                            context=context))
                else:
                    # a service has no stock move
                    move_id = False

        wf_service = netsvc.LocalService("workflow")
        if picking_id:
            wf_service.trg_validate(
                uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
