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
import time
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


class MxStockMove(orm.Model):
    ''' Class for manage stock.move as Accounting
    '''
    
    _name = 'mx.stock.move'
    _description = 'Mx stock move'
    _order = 'date'
    _order = 'date_expected desc, id'
    _log_create = False

    #def _getSSCC(self, cr, uid, context=None):
    #    cr.execute('select id from stock_tracking where create_uid=%s order by id desc limit 1', (uid,))
    #    res = cr.fetchone()
    #    return (res and res[0]) or False

    def name_get(self, cr, uid, ids, context=None):
        res = []
        for line in self.browse(cr, uid, ids, context=context):
            name = line.location_id.name +' > '+line.location_dest_id.name
            if line.product_id.code:
                name = line.product_id.code + ': ' + name
            if line.picking_id.origin:
                name = line.picking_id.origin + '/ ' + name
            res.append((line.id, name))
        return res

    def _check_tracking(self, cr, uid, ids, context=None):
        """ Checks if serial number is assigned to stock move or not.
            @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if not move.prodlot_id and ((
                    (move.product_id.track_production and move.location_id.usage == 'production') or \
                    (move.product_id.track_production and move.location_dest_id.usage == 'production') or \
                    (move.product_id.track_incoming and move.location_id.usage == 'supplier') or \
                    (move.product_id.track_outgoing and move.location_dest_id.usage == 'customer') or \
                    (move.product_id.track_incoming and move.location_id.usage == 'inventory') \
                    )):
                return False
        return True

    def _check_product_lot(self, cr, uid, ids, context=None):
        """ Checks whether move is done or not and production lot is assigned to that move.
            @return: True or False
        """
        for move in self.browse(cr, uid, ids, context=context):
            if move.prodlot_id and move.prodlot_id.product_id.id != move.product_id.id:
                return False
        return True

    _columns = {
        'name': fields.char('Description',  select=True),
        #'priority': fields.selection([('0', 'Not urgent'), ('1', 'Urgent')], 'Priority'),
        'create_date': fields.datetime(
            'Creation Date', readonly=True, select=True),
        'date': fields.datetime(
            'Date',  select=True, 
            help='Move date: scheduled date until move is done, then date of '
                'actual move processing'),
        'date_expected': fields.datetime(
            'Scheduled Date', select=True, 
            help="Scheduled date for the processing of this move"),
        'product_id': fields.many2one(
            'product.product', 'Product',  select=True),

        'product_qty': fields.float(
            'Quantity', 
            digits_compute=dp.get_precision('Product Unit of Measure'),
            help='This is the quantity of products from an inventory '
                'point of view. For moves in the state \'done\', this is the '
                'quantity of products that were actually moved. For other '
                'moves, this is the quantity of product that is planned to '
                'be moved. Lowering this quantity does not generate a '
                'backorder. Changing this quantity on assigned moves affects '
                'the product reservation, and should be done with care.',
        ),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure'),
            
        # TODO remove:
        'product_uos_qty': fields.float('Quantity (UOS)', 
            digits_compute=dp.get_precision('Product Unit of Measure')),
        'product_uos': fields.many2one('product.uom', 'Product UOS'),
        
        'product_packaging': fields.many2one(
            'product.packaging', 'Packaging', 
            help='It specifies attributes of packaging like type, quantity of '
                'packaging,etc.'),

        'location_id': fields.many2one(
            'stock.location', 'Source Location',  select=True,
            help='Sets a location if you produce at a fixed location. This can'
                ' be a partner location if you subcontract the manufacturing'
                ' operations.'),
        'location_dest_id': fields.many2one(
            'stock.location', 'Destination Location', 
            help='Location where the system will stock the finished products'),
        'partner_id': fields.many2one(
            'res.partner', 'Destination Address ', 
            help='Optional address where goods are to be delivered, '
                'specifically used for allotment'),
        'prodlot_id': fields.many2one(
            'stock.production.lot', 'Serial Number', 
            help="Serial number is used to put a serial number on the prod.", 
            select=True),
        'tracking_id': fields.many2one(
            'stock.tracking', 'Pack', select=True, 
            help='Logistical shipping unit: pallet, box, pack ...'),

        #'auto_validate': fields.boolean('Auto Validate'),

        #'move_dest_id': fields.many2one('stock.move', 'Destination Move', 
        #    help="Optional: next stock move when chaining them", select=True),
        #'move_history_ids': fields.many2many('stock.move', 
        #    'stock_move_history_ids', 'parent_id', 'child_id', 
        #    'Move History (child moves)'),
        #'move_history_ids2': fields.many2many('stock.move', 
        #    'stock_move_history_ids', 'child_id', 'parent_id', 
        #    'Move History (parent moves)'),
        'picking_id': fields.many2one('stock.picking', 'Reference', 
            select=True),
        'note': fields.text('Notes'),
        'state': fields.selection([
        #    ('draft', 'New'),
        #    ('cancel', 'Cancelled'),
        #    ('waiting', 'Waiting Another Move'),
        #    ('confirmed', 'Waiting Availability'),
        #    ('assigned', 'Available'),
            ('done', 'Done'),
            ], 'Status', readonly=True, select=True,
        #     help= "* New: When the stock move is created and not yet "
        #           "confirmed.\n"\
        #           "* Waiting Another Move: This state can be seen when a "
        #           "move is waiting for another one, for example in a chained"
        #           " flow.\n"\
        #           "* Waiting Availability: This state is reached when the "
        #           "procurement resolution is not straight forward. It may "
        #           "need the scheduler to run, a component to me "
        #           "manufactured...\n"\
        #           "* Available: When products are reserved, it is set to"
        #           " \'Available\'.\n"\
        #           "* Done: When the shipment is processed, the state is"
        #           " \'Done\'."
            ),
        
        # Price section:    
        'price_unit': fields.float( # base
            'Unit Price', digits_compute= dp.get_precision('Product Price'), 
            help='Technical field used to record the product cost set by the '
                'user during a picking confirmation (when average price '
                'costing method is used)'),
        'price_unit_currency': fields.float( # in different currency
            'Currency unit price', 
            digits_compute= dp.get_precision('Product Price'), 
            help='Currency price'),
        'exchange_currency': fields.float( # in different currency
            'Exchange', digits_compute= dp.get_precision('Product Price'), 
            help='Save the exchange value if use exchange'),
        'price_currency_id': fields.many2one(
            'res.currency', 'Currency for average price', 
            help='Technical field used to record the currency chosen by the '
                'user during a picking confirmation (when average price '
                'costing method is used)'),
                
        'company_id': fields.many2one('res.company', 'Company',  select=True),
        #'backorder_id': fields.related('picking_id','backorder_id', 
        #    type='many2one', relation="stock.picking", 
        #    string="Back Order of", select=True),
        #'origin': fields.related(
        #    'picking_id','origin',type='char', size=64, 
        #    relation="stock.picking", string="Source", store=True),
        'origin': fields.char('Origin', size=20),

        #'scrapped': fields.related('location_dest_id', 'scrap_location', 
        #    type='boolean',relation='stock.location',string='Scrapped', 
        #    readonly=True),
        'type': fields.related('picking_id', 'type', type='selection', 
            selection=[
                ('out', 'Sending Goods'), 
                ('in', 'Getting Goods'), 
                ('internal', 'Internal'), ], string='Shipping Type'),
    }

    def _check_location(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            if record.location_id.usage == 'view':
                raise osv.except_osv(
                    _('Error'), 
                    _('You cannot move product %s from a location of type view %s.') % (
                        record.product_id.name, record.location_id.name))
            if record.location_dest_id.usage == 'view':
                raise osv.except_osv(
                    _('Error'), 
                    _('You cannot move product %s to a location of type view %s.') % (
                        record.product_id.name, 
                        record.location_dest_id.name))
        return True

    _constraints = [
        (
            _check_tracking,
            'You must assign a serial number for this product.',
            ['prodlot_id']),
        (
            _check_location, 
            'You cannot move products from or to a location of the type view.',
            ['location_id','location_dest_id']),
        (
            _check_product_lot,
            'You try to assign a lot which is not from the same product.',
            ['prodlot_id'])
        ]

    #def _default_location_destination(self, cr, uid, context=None):
    #    """ Gets default address of partner for destination location
    #        @return: Address id or False
    #    """
    #    mod_obj = self.pool.get('ir.model.data')
    #    picking_type = context.get('picking_type')
    #    location_id = False
    #    if context is None:
    #        context = {}
    #    if context.get('move_line', []):
    #        if context['move_line'][0]:
    #            if isinstance(context['move_line'][0], (tuple, list)):
    #                location_id = context['move_line'][0][2] and context[
    #                    'move_line'][0][2].get('location_dest_id',False)
    #            else:
    #                move_list = self.pool.get('stock.move').read(
    #                    cr, uid, context['move_line'][0], 
    #                    ['location_dest_id'])
    #                location_id = move_list and move_list[
    #                    'location_dest_id'][0] or False
    #    elif context.get('address_out_id', False):
    #        property_out = self.pool.get('res.partner').browse(
    #            cr, uid, context['address_out_id'], 
    #                context).property_stock_customer
    #        location_id = property_out and property_out.id or False
    #    else:
    #        location_xml_id = False
    #        if picking_type in ('in', 'internal'):
    #            location_xml_id = 'stock_location_stock'
    #        elif picking_type == 'out':
    #            location_xml_id = 'stock_location_customers'
    #        if location_xml_id:
    #            try:
    #                location_model, location_id = mod_obj.get_object_reference(
    #                    cr, uid, 'stock', location_xml_id)
    #                with tools.mute_logger('openerp.osv.orm'):
    #                    self.pool.get('stock.location').check_access_rule(
    #                        cr, uid, [location_id], 'read', context=context)
    #            except (orm.except_orm, ValueError):
    #                location_id = False
    #    return location_id

    #def _default_location_source(self, cr, uid, context=None):
    #    """ Gets default address of partner for source location
    #        @return: Address id or False
    #    """
    #    mod_obj = self.pool.get('ir.model.data')
    #    picking_type = context.get('picking_type')
    #    location_id = False
    #    if context is None:
    #        context = {}
    #    if context.get('move_line', []):
    #        try:
    #            location_id = context['move_line'][0][2]['location_id']
    #        except:
    #            pass
    #    elif context.get('address_in_id', False):
    #        part_obj_add = self.pool.get('res.partner').browse(cr, uid, context['address_in_id'], context=context)
    #        if part_obj_add:
    #            location_id = part_obj_add.property_stock_supplier.id
    #    else:
    #        location_xml_id = False
    #        if picking_type == 'in':
    #            location_xml_id = 'stock_location_suppliers'
    #        elif picking_type in ('out', 'internal'):
    #            location_xml_id = 'stock_location_stock'
    #        if location_xml_id:
    #            try:
    #                location_model, location_id = mod_obj.get_object_reference(cr, uid, 'stock', location_xml_id)
    #                with tools.mute_logger('openerp.osv.orm'):
    #                    self.pool.get('stock.location').check_access_rule(cr, uid, [location_id], 'read', context=context)
    #            except (orm.except_orm, ValueError):
    #                location_id = False
    #    return location_id

    #def _default_destination_address(self, cr, uid, context=None):
    #    user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
    #    return user.company_id.partner_id.id

    #def _default_move_type(self, cr, uid, context=None):
    #    """ Gets default type of move
    #    @return: type
    #    """
    #    if context is None:
    #        context = {}
    #    picking_type = context.get('picking_type')
    #    type = 'internal'
    #    if picking_type == 'in':
    #        type = 'in'
    #    elif picking_type == 'out':
    #        type = 'out'
    #    return type

    _defaults = {
        #'location_id': _default_location_source,
        #'location_dest_id': _default_location_destination,
        #'partner_id': _default_destination_address,
        #'type': _default_move_type,
        'state': 'done',
        #'priority': '1',
        #'product_qty': 1.0,
        #'scrapped' :  False,
        'date': lambda *a: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT),
        'company_id': lambda self,cr,uid,c: self.pool.get(
            'res.company')._company_default_get(
                cr, uid, 'stock.move', context=c),
        'date_expected': lambda *a: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT),
        }

    def write(self, cr, uid, ids, vals, context=None):
        # TODO needed if not workflow
        if isinstance(ids, (int, long)):
            ids = [ids]
        if uid != 1:
            frozen_fields = set([
                'product_qty', 'product_uom', 'product_uos_qty', 
                'product_uos', 'location_id', 'location_dest_id', 'product_id',
                ])
            for move in self.browse(cr, uid, ids, context=context):
                if frozen_fields.intersection(vals):
                    raise osv.except_osv(
                        _('Operation Forbidden!'),
                        _('Quantities, Units of Measure, Products and '
                            'Locations cannot be modified on stock moves that '
                            'have already been processed (except by the '
                            'Administrator).'))
        return  super(stock_move, self).write(cr, uid, ids, vals, context=context)

    #def copy_data(self, cr, uid, id, default=None, context=None):
    #    if default is None:
    #        default = {}
    #    default = default.copy()
    #    default.setdefault('tracking_id', False)
    #    default.setdefault('prodlot_id', False)
    #    default.setdefault('move_history_ids', [])
    #    default.setdefault('move_history_ids2', [])
    #    return super(stock_move, self).copy_data(cr, uid, id, default, context=context)

    #def _auto_init(self, cursor, context=None):
    #    res = super(stock_move, self)._auto_init(cursor, context=context)
    #    cursor.execute('SELECT indexname \
    #            FROM pg_indexes \
    #            WHERE indexname = \'stock_move_location_id_location_dest_id_product_id_state\'')
    #    if not cursor.fetchone():
    #        cursor.execute('CREATE INDEX stock_move_location_id_location_dest_id_product_id_state \
    #                ON stock_move (product_id, state, location_id, location_dest_id)')
    #    return res

    def onchange_lot_id(self, cr, uid, ids, prodlot_id=False, 
            product_qty=False, loc_id=False, product_id=False, uom_id=False, 
            context=None):
        """ On change of production lot gives a warning message.
        @param prodlot_id: Changed production lot id
        @param product_qty: Quantity of product
        @param loc_id: Location id
        @param product_id: Product id
        @return: Warning message
        """
        
        if not prodlot_id or not loc_id:
            return {}
        ctx = context and context.copy() or {}
        ctx['location_id'] = loc_id
        ctx.update({'raise-exception': True})
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        product_uom = product_obj.browse(
            cr, uid, product_id, context=ctx).uom_id
        prodlot = self.pool.get('stock.production.lot').browse(
            cr, uid, prodlot_id, context=ctx)
        location = self.pool.get('stock.location').browse(
            cr, uid, loc_id, context=ctx)
        uom = uom_obj.browse(cr, uid, uom_id, context=ctx)
        amount_actual = uom_obj._compute_qty_obj(
            cr, uid, product_uom, prodlot.stock_available, uom, context=ctx)
        warning = {}
        if (location.usage == 'internal') and (
                product_qty > (amount_actual or 0.0)):
            warning = {
                'title': _(
                    'Insufficient Stock for Serial Number !'),
                'message': _(
                    'You are moving %.2f %s but only %.2f %s available for '
                    'this serial number.') % (
                        product_qty, uom.name, amount_actual, uom.name)
            }
        return {'warning': warning}

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty,
            product_uom, product_uos):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_qty: Changed Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'product_uos_qty': 0.00
            }
        warning = {}

        if (not product_id) or (product_qty <=0.0):
            result['product_qty'] = 0.0
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])
        
        # Warn if the quantity was decreased 
        if ids:
            for move in self.read(cr, uid, ids, ['product_qty']):
                if product_qty < move['product_qty']:
                    warning.update({
                       'title': _('Information'),
                       'message': _(
                           "By changing this quantity here, you accept the "
                           "new quantity as complete: OpenERP will not "
                           "automatically generate a back order.") })
                break

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_uos_qty'] = product_qty * uos_coeff['uos_coeff']
        else:
            result['product_uos_qty'] = product_qty

        return {'value': result, 'warning': warning}

    def onchange_uos_quantity(self, cr, uid, ids, product_id, product_uos_qty,
            product_uos, product_uom):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_uos_qty: Changed UoS Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'product_qty': 0.00
            }
        warning = {}

        if (not product_id) or (product_uos_qty <= 0.0):
            result['product_uos_qty'] = 0.0
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])
        
        # Warn if the quantity was decreased 
        for move in self.read(cr, uid, ids, ['product_uos_qty']):
            if product_uos_qty < move['product_uos_qty']:
                warning.update({
                   'title': _('Warning: No Back Order'),
                   'message': _(
                       "By changing the quantity here, you accept the"
                       " new quantity as complete: OpenERP will not "
                       "automatically generate a Back Order.") })
                break

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_qty'] = product_uos_qty / uos_coeff['uos_coeff']
        else:
            result['product_qty'] = product_uos_qty
        return {'value': result, 'warning': warning}

    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, partner_id=False):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quant.
            @param prod_id: Changed Product id
            @param loc_id: Source location id
            @param loc_dest_id: Destination location id
            @param partner_id: Address id of partner
            @return: Dictionary of values
        """
        if not prod_id:
            return {}
        user = self.pool.get('res.users').browse(cr, uid, uid)
        lang = user and user.lang or False
        if partner_id:
            addr_rec = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if addr_rec:
                lang = addr_rec and addr_rec.lang or False
        ctx = {'lang': lang}

        product = self.pool.get('product.product').browse(
            cr, uid, [prod_id], context=ctx)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'product_qty': 1.00,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(
                cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)[
                    'value']['product_uos_qty'],
            'prodlot_id' : False,
            }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
        return {'value': result}

    def onchange_move_type(self, cr, uid, ids, type, context=None):
        """ On change of move type gives sorce and destination location.
            @param type: Move Type
            @return: Dictionary of values
        """
        mod_obj = self.pool.get('ir.model.data')
        location_source_id = 'stock_location_stock'
        location_dest_id = 'stock_location_stock'
        if type == 'in':
            location_source_id = 'stock_location_suppliers'
            location_dest_id = 'stock_location_stock'
        elif type == 'out':
            location_source_id = 'stock_location_stock'
            location_dest_id = 'stock_location_customers'
        try:
            source_location = mod_obj.get_object_reference(
                cr, uid, 'stock', location_source_id)
            with tools.mute_logger('openerp.osv.orm'):
                self.pool.get('stock.location').check_access_rule(
                    cr, uid, [source_location[1]], 'read', context=context)
        except (orm.except_orm, ValueError):
            source_location = False
        try:
            dest_location = mod_obj.get_object_reference(
                cr, uid, 'stock', location_dest_id)
            with tools.mute_logger('openerp.osv.orm'):
                self.pool.get('stock.location').check_access_rule(
                    cr, uid, [dest_location[1]], 'read', context=context)
        except (orm.except_orm, ValueError):
            dest_location = False
        return {'value': {
            'location_id': source_location and source_location[1] or False, 
            'location_dest_id': dest_location and dest_location[1] or False}}

    def onchange_date(self, cr, uid, ids, date, date_expected, context=None):
        """ On change of Scheduled Date gives a Move date.
            @param date_expected: Scheduled Date
            @param date: Move Date
            @return: Move Date
        """
        if not date_expected:
            date_expected = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return {'value':{'date': date_expected}}

    def _chain_compute(self, cr, uid, moves, context=None):
        """ Finds whether the location has chained location type or not.
            @param moves: Stock moves
            @return: Dictionary containing destination location with chained location type.
        """
        result = {}
        for m in moves:
            dest = self.pool.get('stock.location').chained_location_get(
                cr,
                uid,
                m.location_dest_id,
                m.picking_id and m.picking_id.partner_id and \
                    m.picking_id.partner_id,
                m.product_id,
                context
            )
            if dest:
                if dest[1] == 'transparent':
                    newdate = (datetime.strptime(
                        m.date, '%Y-%m-%d %H:%M:%S') + relativedelta(
                            days=dest[2] or 0)).strftime(
                                DEFAULT_SERVER_DATE_FORMAT)
                    self.write(cr, uid, [m.id], {
                        'date': newdate,
                        'location_dest_id': dest[0].id})
                    if m.picking_id and (dest[3] or dest[5]):
                        self.pool.get('stock.picking').write(
                            cr, uid, [m.picking_id.id], {
                                'stock_journal_id': 
                                    dest[3] or m.picking_id.stock_journal_id.id,
                                'type': dest[5] or m.picking_id.type
                        }, context=context)
                    m.location_dest_id = dest[0]
                    res2 = self._chain_compute(cr, uid, [m], context=context)
                    for pick_id in res2.keys():
                        result.setdefault(pick_id, [])
                        result[pick_id] += res2[pick_id]
                else:
                    result.setdefault(m.picking_id, [])
                    result[m.picking_id].append( (m, dest) )
        return result

    def _prepare_chained_picking(self, cr, uid, picking_name, picking, 
            picking_type, moves_todo, context=None):
        """Prepare the definition (values) to create a new chained picking.

           :param str picking_name: desired new picking name
           :param browse_record picking: source picking (being chained to)
           :param str picking_type: desired new picking type
           :param list moves_todo: specification of the stock moves to be later included in this
               picking, in the form::

                   [[move, (dest_location, auto_packing, chained_delay, chained_journal,
                                  chained_company_id, chained_picking_type)],
                    ...
                   ]

               See also :meth:`stock_location.chained_location_get`.
        """
        res_company = self.pool.get('res.company')
        return {
            'name': picking_name,
            'origin': tools.ustr(picking.origin or ''),
            'type': picking_type,
            'note': picking.note,
            'move_type': picking.move_type,
            'auto_picking': moves_todo[0][1][1] == 'auto',
            'stock_journal_id': moves_todo[0][1][3],
            'company_id': 
                moves_todo[0][1][4] or res_company._company_default_get(
                    cr, uid, 'stock.company', context=context),
            'partner_id': picking.partner_id.id,
            'invoice_state': 'none',
            'date': picking.date,
            }

    def _create_chained_picking(self, cr, uid, picking_name, picking, 
            picking_type, moves_todo, context=None):
        picking_obj = self.pool.get('stock.picking')
        return picking_obj.create(cr, uid, self._prepare_chained_picking(
            cr, uid, picking_name, picking, picking_type, moves_todo, 
            context=context))

    def create_chained_picking(self, cr, uid, moves, context=None):
        res_obj = self.pool.get('res.company')
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        new_moves = []
        if context is None:
            context = {}
        seq_obj = self.pool.get('ir.sequence')
        for picking, chained_moves in self._chain_compute(
                cr, uid, moves, context=context).items():
            # We group the moves by automatic move type, 
            # so it creates different pickings for different types
            moves_by_type = {}
            for move in chained_moves:
                moves_by_type.setdefault(move[1][1], []).append(move)
            for todo in moves_by_type.values():
                ptype = todo[0][1][5] and todo[0][1][5] or location_obj.picking_type_get(cr, uid, todo[0][0].location_dest_id, todo[0][1][0])
                if picking:
                    # name of new picking according to its type
                    if ptype == 'internal':
                        new_pick_name = seq_obj.get(cr, uid,'stock.picking')
                    else :
                        new_pick_name = seq_obj.get(
                             cr, uid, 'stock.picking.' + ptype)
                    pickid = self._create_chained_picking(
                        cr, uid, new_pick_name, picking, ptype, todo, 
                        context=context)
                    # Need to check name of old picking because it always 
                    # considers picking as "OUT" when created from Sales Order
                    old_ptype = location_obj.picking_type_get(
                        cr, uid, picking.move_lines[0].location_id, 
                        picking.move_lines[0].location_dest_id)
                    if old_ptype != picking.type:
                        old_pick_name = seq_obj.get(
                            cr, uid, 'stock.picking.' + old_ptype)
                        self.pool.get('stock.picking').write(
                            cr, uid, [picking.id], {
                                'name': old_pick_name, 'type': old_ptype}, 
                            context=context)
                else:
                    pickid = False
                for move, (loc, dummy, delay, dummy, company_id, ptype, 
                        invoice_state) in todo:
                    new_id = move_obj.copy(cr, uid, move.id, {
                        'location_id': move.location_dest_id.id,
                        'location_dest_id': loc.id,
                        'date': datetime.now().strftime(
                            DEFAULT_SERVER_DATE_FORMAT),
                        'picking_id': pickid,
                        #'state': 'waiting',
                        'company_id': company_id or res_obj._company_default_get(
                            cr, uid, 'stock.company', context=context),
                        'move_history_ids': [],
                        'date_expected': (datetime.strptime(
                            move.date, 
                            DEFAULT_SERVER_DATETIME_FORMAT) + relativedelta(
                                days=delay or 0)).strftime(DEFAULT_SERVER_DATE_FORMAT),
                        'move_history_ids2': []}
                    )
                    move_obj.write(cr, uid, [move.id], {
                        'move_dest_id': new_id,
                        'move_history_ids': [(4, new_id)]
                    })
                    new_moves.append(self.browse(cr, uid, [new_id])[0])
                if pickid:
                    wf_service.trg_validate(
                        uid, 'stock.picking', pickid, 'button_confirm', cr)
        if new_moves:
            new_moves += self.create_chained_picking(cr, uid, new_moves, context)
        return new_moves

    #def action_confirm(self, cr, uid, ids, context=None):
    #    """ Confirms stock move.
    #    @return: List of ids.
    #    """
    #    moves = self.browse(cr, uid, ids, context=context)
    #    self.write(cr, uid, ids, {'state': 'confirmed'})
    #    self.create_chained_picking(cr, uid, moves, context)
    #    return []
    #def action_assign(self, cr, uid, ids, *args):
    #    """ Changes state to confirmed or waiting.
    #    @return: List of values
    #    """
    #    todo = []
    #    for move in self.browse(cr, uid, ids):
    #        if move.state in ('confirmed', 'waiting'):
    #            todo.append(move.id)
    #    res = self.check_assign(cr, uid, todo)
    #    return res
    #def force_assign(self, cr, uid, ids, context=None):
    #    """ Changes the state to assigned.
    #    @return: True
    #    """
    #    self.write(cr, uid, ids, {'state': 'assigned'})
    #    wf_service = netsvc.LocalService('workflow')
    #    for move in self.browse(cr, uid, ids, context):
    #        if move.picking_id:
    #            wf_service.trg_write(uid, 'stock.picking', move.picking_id.id, cr)
    #    return True
    #def cancel_assign(self, cr, uid, ids, context=None):
    #    """ Changes the state to confirmed.
    #    @return: True
    #    """
    #    self.write(cr, uid, ids, {'state': 'confirmed'})
    #    # fix for bug lp:707031
    #    # called write of related picking because changing move availability does
    #    # not trigger workflow of picking in order to change the state of picking
    #    wf_service = netsvc.LocalService('workflow')
    #    for move in self.browse(cr, uid, ids, context):
    #        if move.picking_id:
    #            wf_service.trg_write(uid, 'stock.picking', move.picking_id.id, cr)
    #    return True

    #
    # Duplicate stock.move
    #
    def check_assign(self, cr, uid, ids, context=None):
        """ Checks the product type and accordingly writes the state.
            @return: No. of moves done
        """
        done = []
        count = 0
        pickings = {}
        if context is None:
            context = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.product_id.type == 'consu' or move.location_id.usage == 'supplier':
                if move.state in ('confirmed', 'waiting'):
                    done.append(move.id)
                pickings[move.picking_id.id] = 1
                continue
            if move.state in ('confirmed', 'waiting'):
                # Important: we must pass lock=True to _product_reserve() to avoid race conditions and double reservations
                res = self.pool.get('stock.location')._product_reserve(cr, uid, [move.location_id.id], move.product_id.id, move.product_qty, {'uom': move.product_uom.id}, lock=True)
                if res:
                    #_product_available_test depends on the next status for correct functioning
                    #the test does not work correctly if the same product occurs multiple times
                    #in the same order. This is e.g. the case when using the button 'split in two' of
                    #the stock outgoing form
                    self.write(cr, uid, [move.id], {'state':'assigned'})
                    done.append(move.id)
                    pickings[move.picking_id.id] = 1
                    r = res.pop(0)
                    product_uos_qty = self.pool.get('stock.move').onchange_quantity(cr, uid, ids, move.product_id.id, r[0], move.product_id.uom_id.id, move.product_id.uos_id.id)['value']['product_uos_qty']
                    cr.execute('update stock_move set location_id=%s, product_qty=%s, product_uos_qty=%s where id=%s', (r[1], r[0],product_uos_qty, move.id))

                    while res:
                        r = res.pop(0)
                        product_uos_qty = self.pool.get('stock.move').onchange_quantity(cr, uid, ids, move.product_id.id, r[0], move.product_id.uom_id.id, move.product_id.uos_id.id)['value']['product_uos_qty']
                        move_id = self.copy(cr, uid, move.id, {'product_uos_qty': product_uos_qty, 'product_qty': r[0], 'location_id': r[1]})
                        done.append(move_id)
        if done:
            count += len(done)
            self.write(cr, uid, done, {'state': 'assigned'})

        if count:
            for pick_id in pickings:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        return count

    def setlast_tracking(self, cr, uid, ids, context=None):
        tracking_obj = self.pool.get('stock.tracking')
        picking = self.browse(cr, uid, ids, context=context)[0].picking_id
        if picking:
            last_track = [line.tracking_id.id for line in picking.move_lines if line.tracking_id]
            if not last_track:
                last_track = tracking_obj.create(cr, uid, {}, context=context)
            else:
                last_track.sort()
                last_track = last_track[-1]
            self.write(cr, uid, ids, {'tracking_id': last_track})
        return True

    #
    # Cancel move => cancel others move and pickings
    #
    #def action_cancel(self, cr, uid, ids, context=None):
    #    """ Cancels the moves and if all moves are cancelled it cancels the picking.
    #    @return: True
    #    """
    #    if not len(ids):
    #        return True
    #    if context is None:
    #        context = {}
    #    pickings = set()
    #    for move in self.browse(cr, uid, ids, context=context):
    #        if move.state in ('confirmed', 'waiting', 'assigned', 'draft'):
    #            if move.picking_id:
    #                pickings.add(move.picking_id.id)
    #        if move.move_dest_id and move.move_dest_id.state == 'waiting':
    #            self.write(cr, uid, [move.move_dest_id.id], {'state': 'confirmed'}, context=context)
    #            if context.get('call_unlink',False) and move.move_dest_id.picking_id:
    #                wf_service = netsvc.LocalService("workflow")
    #                wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
    #    self.write(cr, uid, ids, {'state': 'cancel', 'move_dest_id': False}, context=context)
    #    if not context.get('call_unlink',False):
    #        for pick in self.pool.get('stock.picking').browse(cr, uid, list(pickings), context=context):
    #            if all(move.state == 'cancel' for move in pick.move_lines):
    #                self.pool.get('stock.picking').write(cr, uid, [pick.id], {'state': 'cancel'}, context=context)
    #    wf_service = netsvc.LocalService("workflow")
    #    for id in ids:
    #        wf_service.trg_trigger(uid, 'stock.move', id, cr)
    #    return True

    def _get_accounting_data_for_valuation(self, cr, uid, move, context=None):
        """
        Return the accounts and journal to use to post Journal Entries for the real-time
        valuation of the move.

        :param context: context dictionary that can explicitly mention the company to consider via the 'force_company' key
        :raise: osv.except_osv() is any mandatory account or journal is not defined.
        """
        product_obj=self.pool.get('product.product')
        accounts = product_obj.get_product_accounts(cr, uid, move.product_id.id, context)
        if move.location_id.valuation_out_account_id:
            acc_src = move.location_id.valuation_out_account_id.id
        else:
            acc_src = accounts['stock_account_input']

        if move.location_dest_id.valuation_in_account_id:
            acc_dest = move.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts['stock_account_output']

        acc_valuation = accounts.get('property_stock_valuation_account_id', False)
        journal_id = accounts['stock_journal']

        if acc_dest == acc_valuation:
            raise osv.except_osv(_('Error!'),  _('Cannot create Journal Entry, Output Account of this product and Valuation account on category of this product are same.'))

        if acc_src == acc_valuation:
            raise osv.except_osv(_('Error!'),  _('Cannot create Journal Entry, Input Account of this product and Valuation account on category of this product are same.'))

        if not acc_src:
            raise osv.except_osv(_('Error!'),  _('Please define stock input account for this product or its category: "%s" (id: %d)') % \
                                    (move.product_id.name, move.product_id.id,))
        if not acc_dest:
            raise osv.except_osv(_('Error!'),  _('Please define stock output account for this product or its category: "%s" (id: %d)') % \
                                    (move.product_id.name, move.product_id.id,))
        if not journal_id:
            raise osv.except_osv(_('Error!'), _('Please define journal on the product category: "%s" (id: %d)') % \
                                    (move.product_id.categ_id.name, move.product_id.categ_id.id,))
        if not acc_valuation:
            raise osv.except_osv(_('Error!'), _('Please define inventory valuation account on the product category: "%s" (id: %d)') % \
                                    (move.product_id.categ_id.name, move.product_id.categ_id.id,))
        return journal_id, acc_src, acc_dest, acc_valuation

    def _get_reference_accounting_values_for_valuation(self, cr, uid, move, context=None):
        """ Return the reference amount and reference currency representing the 
            inventory valuation for this move.
            These reference values should possibly be converted before being 
            posted in Journals to adapt to the primary and secondary currencies 
            of the relevant accounts.
        """
        product_uom_obj = self.pool.get('product.uom')

        # by default the reference currency is that of the move's company
        reference_currency_id = move.company_id.currency_id.id

        default_uom = move.product_id.uom_id.id
        qty = product_uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, default_uom)

        # if product is set to average price and a specific value was entered in the picking wizard,
        # we use it
        if move.location_dest_id.usage != 'internal' and move.product_id.cost_method == 'average':
            reference_amount = qty * move.product_id.standard_price
        elif move.product_id.cost_method == 'average' and move.price_unit:
            reference_amount = qty * move.price_unit
            reference_currency_id = move.price_currency_id.id or reference_currency_id

        # Otherwise we default to the company's valuation price type, 
        # considering that the values of the valuation field are expressed in 
        # the default currency of the move's company.
        else:
            if context is None:
                context = {}
            currency_ctx = dict(context, currency_id = move.company_id.currency_id.id)
            amount_unit = move.product_id.price_get(
                'standard_price', context=currency_ctx)[move.product_id.id]
            reference_amount = amount_unit * qty

        return reference_amount, reference_currency_id


    def _create_product_valuation_moves(self, cr, uid, move, context=None):
        """
        Generate the appropriate accounting moves if the product being moves is subject
        to real_time valuation tracking, and the source or destination location is
        a transit location or is outside of the company.
        """
        if move.product_id.valuation == 'real_time': # FIXME: product valuation should perhaps be a property?
            if context is None:
                context = {}
            src_company_ctx = dict(context,force_company=move.location_id.company_id.id)
            dest_company_ctx = dict(context,force_company=move.location_dest_id.company_id.id)
            account_moves = []
            # Outgoing moves (or cross-company output part)
            if move.location_id.company_id \
                and (move.location_id.usage == 'internal' and move.location_dest_id.usage != 'internal'\
                     or move.location_id.company_id != move.location_dest_id.company_id):
                journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, src_company_ctx)
                reference_amount, reference_currency_id = self._get_reference_accounting_values_for_valuation(cr, uid, move, src_company_ctx)
                #returning goods to supplier
                if move.location_dest_id.usage == 'supplier':
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, acc_valuation, acc_src, reference_amount, reference_currency_id, context))]
                else:
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, acc_valuation, acc_dest, reference_amount, reference_currency_id, context))]

            # Incoming moves (or cross-company input part)
            if move.location_dest_id.company_id \
                and (move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal'\
                     or move.location_id.company_id != move.location_dest_id.company_id):
                journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, dest_company_ctx)
                reference_amount, reference_currency_id = self._get_reference_accounting_values_for_valuation(cr, uid, move, src_company_ctx)
                #goods return from customer
                if move.location_id.usage == 'customer':
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, acc_dest, acc_valuation, reference_amount, reference_currency_id, context))]
                else:
                    account_moves += [(journal_id, self._create_account_move_line(cr, uid, move, acc_src, acc_valuation, reference_amount, reference_currency_id, context))]

            move_obj = self.pool.get('account.move')
            for j_id, move_lines in account_moves:
                move_obj.create(cr, uid,
                        {
                         'journal_id': j_id,
                         'line_id': move_lines,
                         'ref': move.picking_id and move.picking_id.name}, context=context)

    #def action_done(self, cr, uid, ids, context=None):
    #    """ Makes the move done and if all moves are done, it will finish the picking.
    #    @return:
    #    """
    #    picking_ids = []
    #    move_ids = []
    #    wf_service = netsvc.LocalService("workflow")
    #    if context is None:
    #        context = {}
    #    todo = []
    #    for move in self.browse(cr, uid, ids, context=context):
    #        if move.state=="draft":
    #            todo.append(move.id)
    #    if todo:
    #        self.action_confirm(cr, uid, todo, context=context)
    #        todo = []
    #    for move in self.browse(cr, uid, ids, context=context):
    #        if move.state in ['done','cancel']:
    #            continue
    #        move_ids.append(move.id)
    #        if move.picking_id:
    #            picking_ids.append(move.picking_id.id)
    #        if move.move_dest_id.id and (move.state != 'done'):
    #            # Downstream move should only be triggered if this move is the last pending upstream move
    #            other_upstream_move_ids = self.search(cr, uid, [('id','!=',move.id),('state','not in',['done','cancel']),
    #                                        ('move_dest_id','=',move.move_dest_id.id)], context=context)
    #            if not other_upstream_move_ids:
    #                self.write(cr, uid, [move.id], {'move_history_ids': [(4, move.move_dest_id.id)]})
    #                if move.move_dest_id.state in ('waiting', 'confirmed'):
    #                    self.force_assign(cr, uid, [move.move_dest_id.id], context=context)
    #                    if move.move_dest_id.picking_id:
    #                        wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
    #                    if move.move_dest_id.auto_validate:
    #                        self.action_done(cr, uid, [move.move_dest_id.id], context=context)
    #        self._create_product_valuation_moves(cr, uid, move, context=context)
    #        if move.state not in ('confirmed','done','assigned'):
    #            todo.append(move.id)
    #    if todo:
    #        self.action_confirm(cr, uid, todo, context=context)
    #    self.write(cr, uid, move_ids, {'state': 'done', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
    #    for id in move_ids:
    #         wf_service.trg_trigger(uid, 'stock.move', id, cr)
    #    for pick_id in picking_ids:
    #        wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
    #    return True

    def _create_account_move_line(self, cr, uid, move, src_account_id, dest_account_id, reference_amount, reference_currency_id, context=None):
        """
        Generate the account.move.line values to post to track the stock 
        valuation difference due to the processing of the given stock move.
        """
        # prepare default values considering that the destination accounts have the reference_currency_id as their main currency
        partner_id = (move.picking_id.partner_id and self.pool.get(
            'res.partner')._find_accounting_partner(
                move.picking_id.partner_id).id) or False
        debit_line_vals = {
            'name': move.name,
            'product_id': move.product_id and move.product_id.id or False,
            'quantity': move.product_qty,
            'ref': move.picking_id and move.picking_id.name or False,
            'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
            'partner_id': partner_id,
            'debit': reference_amount,
            'account_id': dest_account_id,
            }
        credit_line_vals = {
            'name': move.name,
            'product_id': move.product_id and move.product_id.id or False,
            'quantity': move.product_qty,
            'ref': move.picking_id and move.picking_id.name or False,
            'date': datetime.now().strftime(DEFAULT_SERVER_DATE_FORMAT),
            'partner_id': partner_id,
            'credit': reference_amount,
            'account_id': src_account_id,
            }

        # if we are posting to accounts in a different currency, provide 
        # correct values in both currencies correctly
        # when compatible with the optional secondary currency on the account.
        # Financial Accounts only accept amounts in secondary currencies if 
        # there's no secondary currency on the account
        # or if it's the same as that of the secondary amount being posted.
        account_obj = self.pool.get('account.account')
        src_acct, dest_acct = account_obj.browse(cr, uid, [
            src_account_id, dest_account_id], context=context)
        src_main_currency_id = src_acct.company_id.currency_id.id
        dest_main_currency_id = dest_acct.company_id.currency_id.id
        cur_obj = self.pool.get('res.currency')
        if reference_currency_id != src_main_currency_id:
            # fix credit line:
            credit_line_vals['credit'] = cur_obj.compute(
                cr, uid, reference_currency_id, src_main_currency_id, 
                reference_amount, context=context)
            if (not src_acct.currency_id) or src_acct.currency_id.id == reference_currency_id:
                credit_line_vals.update(currency_id=reference_currency_id, amount_currency= -reference_amount)
        if reference_currency_id != dest_main_currency_id:
            # fix debit line:
            debit_line_vals['debit'] = cur_obj.compute(
                cr, uid, reference_currency_id, dest_main_currency_id, 
                reference_amount, context=context)
            if (not dest_acct.currency_id) or dest_acct.currency_id.id == reference_currency_id:
                debit_line_vals.update(
                    currency_id=reference_currency_id, 
                    amount_currency=reference_amount)

        return [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        for move in self.browse(cr, uid, ids, context=context):
            if not ctx.get('call_unlink', False):
                raise osv.except_osv(
                    _('User Error!'), 
                    _('You can only delete draft moves.'))
        return super(stock_move, self).unlink(
            cr, uid, ids, context=ctx)

    # _create_lot function is not used anywhere
    def _create_lot(self, cr, uid, ids, product_id, prefix=False):
        """ Creates production lot
            @return: Production lot id
        """
        prodlot_obj = self.pool.get('stock.production.lot')
        prodlot_id = prodlot_obj.create(cr, uid, {
            'prefix': prefix, 'product_id': product_id})
        return prodlot_id

    def action_scrap(self, cr, uid, ids, quantity, location_id, context=None):
        """ Move the scrap/damaged product into scrap location
            @param cr: the database cursor
            @param uid: the user id
            @param ids: ids of stock move object to be scrapped
            @param quantity : specify scrap qty
            @param location_id : specify scrap location
            @param context: context arguments
            @return: Scraped lines
        """
        #quantity should in MOVE UOM
        if quantity <= 0:
            raise osv.except_osv(
                _('Warning!'), 
                _('Please provide a positive quantity to scrap.'))
        res = []
        for move in self.browse(cr, uid, ids, context=context):
            source_location = move.location_id
            if move.state == 'done':
                source_location = move.location_dest_id
            if source_location.usage != 'internal':
                #restrict to scrap from a virtual location because it's meaningless and it may introduce errors in stock ('creating' new products from nowhere)
                raise osv.except_osv(
                    _('Error!'), 
                    _('Forbidden operation: it is not allowed to scrap '
                        'products from a virtual location.'))
            move_qty = move.product_qty
            uos_qty = quantity / move_qty * move.product_uos_qty
            default_val = {
                'location_id': source_location.id,
                'product_qty': quantity,
                'product_uos_qty': uos_qty,
                'state': move.state,
                'scrapped': True,
                'location_dest_id': location_id,
                'tracking_id': move.tracking_id.id,
                'prodlot_id': move.prodlot_id.id,
            }
            new_move = self.copy(cr, uid, move.id, default_val)

            res += [new_move]
            product_obj = self.pool.get('product.product')
            for product in product_obj.browse(cr, uid, [move.product_id.id], context=context):
                if move.picking_id:
                    uom = product.uom_id.name if product.uom_id else ''
                    message = _("%s %s %s has been <b>moved to</b> scrap.") % (quantity, uom, product.name)
                    move.picking_id.message_post(body=message)

        self.action_done(cr, uid, res, context=context)
        return res

    # action_split function is not used anywhere
    # FIXME: deprecate this method
    def action_split(self, cr, uid, ids, quantity, split_by_qty=1, 
            prefix=False, with_lot=True, context=None):
        """ Split Stock Move lines into production lot which specified split 
            by quantity.
            @param cr: the database cursor
            @param uid: the user id
            @param ids: ids of stock move object to be splited
            @param split_by_qty : specify split by qty
            @param prefix : specify prefix of production lot
            @param with_lot : if true, prodcution lot will assign for split 
                line otherwise not.
            @param context: context arguments
            @return: Splited move lines
        """

        if context is None:
            context = {}
        if quantity <= 0:
            raise osv.except_osv(
                _('Warning!'), 
                _('Please provide proper quantity.'))

        res = []

        for move in self.browse(cr, uid, ids, context=context):
            if split_by_qty <= 0 or quantity == 0:
                return res

            uos_qty = split_by_qty / move.product_qty * move.product_uos_qty

            quantity_rest = quantity % split_by_qty
            uos_qty_rest = split_by_qty / move.product_qty * move.product_uos_qty

            update_val = {
                'product_qty': split_by_qty,
                'product_uos_qty': uos_qty,
            }
            for idx in range(int(quantity//split_by_qty)):
                if not idx and move.product_qty<=quantity:
                    current_move = move.id
                else:
                    current_move = self.copy(
                        cr, uid, move.id, {'state': move.state})
                res.append(current_move)
                if with_lot:
                    update_val['prodlot_id'] = self._create_lot(
                        cr, uid, [current_move], move.product_id.id)

                self.write(cr, uid, [current_move], update_val)


            if quantity_rest > 0:
                idx = int(quantity // split_by_qty)
                update_val['product_qty'] = quantity_rest
                update_val['product_uos_qty'] = uos_qty_rest
                if not idx and move.product_qty <= quantity:
                    current_move = move.id
                else:
                    current_move = self.copy(
                        cr, uid, move.id, {'state': move.state})

                res.append(current_move)

                if with_lot:
                    update_val['prodlot_id'] = self._create_lot(
                        cr, uid, [current_move], move.product_id.id)

                self.write(cr, uid, [current_move], update_val)
        return res

    def action_consume(self, cr, uid, ids, quantity, location_id=False, 
            context=None):
        """ Consumed product with specific quatity from specific source location
            @param cr: the database cursor
            @param uid: the user id
            @param ids: ids of stock move object to be consumed
            @param quantity : specify consume quantity
            @param location_id : specify source location
            @param context: context arguments
            @return: Consumed lines
        """
        #quantity should in MOVE UOM
        if context is None:
            context = {}
        if quantity <= 0:
            raise osv.except_osv(
                _('Warning!'), 
                _('Please provide proper quantity.'))
        res = []
        for move in self.browse(cr, uid, ids, context=context):
            move_qty = move.product_qty
            if move_qty <= 0:
                raise osv.except_osv(
                    _('Error!'), 
                    _('Cannot consume a move with negative or zero quantity.'))
            quantity_rest = move.product_qty
            quantity_rest -= quantity
            uos_qty_rest = quantity_rest / move_qty * move.product_uos_qty
            if quantity_rest <= 0:
                quantity_rest = 0
                uos_qty_rest = 0
                quantity = move.product_qty

            uos_qty = quantity / move_qty * move.product_uos_qty
            if float_compare(quantity_rest, 0, precision_rounding=move.product_id.uom_id.rounding):
                default_val = {
                    'product_qty': quantity,
                    'product_uos_qty': uos_qty,
                    'state': move.state,
                    'location_id': location_id or move.location_id.id,
                    }
                current_move = self.copy(cr, uid, move.id, default_val)
                res += [current_move]
                update_val = {}
                update_val['product_qty'] = quantity_rest
                update_val['product_uos_qty'] = uos_qty_rest
                self.write(cr, uid, [move.id], update_val)

            else:
                quantity_rest = quantity
                uos_qty_rest =  uos_qty
                res += [move.id]
                update_val = {
                        'product_qty' : quantity_rest,
                        'product_uos_qty' : uos_qty_rest,
                        'location_id': location_id or move.location_id.id,
                }
                self.write(cr, uid, [move.id], update_val)

        self.action_done(cr, uid, res, context=context)

        return res

    # FIXME: needs refactoring, this code is partially duplicated in stock_picking.do_partial()!
    def do_partial(self, cr, uid, ids, partial_datas, context=None):
        """ Makes partial pickings and moves done.
            @param partial_datas: Dictionary containing details of partial picking
                like partner_id, delivery_date, delivery
                moves with product_id, product_qty, uom
        """
        res = {}
        picking_obj = self.pool.get('stock.picking')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        uom_obj = self.pool.get('product.uom')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        complete, too_many, too_few = [], [], []
        move_product_qty = {}
        prodlot_ids = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            partial_data = partial_datas.get('move%s'%(move.id), False)
            assert partial_data, _(
                'Missing partial picking data for move #%s.') % move.id
            product_qty = partial_data.get('product_qty',0.0)
            move_product_qty[move.id] = product_qty
            product_uom = partial_data.get('product_uom',False)
            product_price = partial_data.get('product_price',0.0)
            product_currency = partial_data.get('product_currency',False)
            prodlot_ids[move.id] = partial_data.get('prodlot_id')
            if move.product_qty == product_qty:
                complete.append(move)
            elif move.product_qty > product_qty:
                too_few.append(move)
            else:
                too_many.append(move)

            # Average price computation
            if (move.picking_id.type == 'in') and (
                    move.product_id.cost_method == 'average'):
                product = product_obj.browse(cr, uid, move.product_id.id)
                move_currency_id = move.company_id.currency_id.id
                context['currency_id'] = move_currency_id
                qty = uom_obj._compute_qty(
                    cr, uid, product_uom, product_qty, product.uom_id.id)
                if qty > 0:
                    new_price = currency_obj.compute(cr, uid, product_currency,
                            move_currency_id, product_price, round=False)
                    new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                            product.uom_id.id)
                    if product.qty_available <= 0:
                        new_std_price = new_price
                    else:
                        # Get the standard price
                        amount_unit = product.price_get(
                            'standard_price', context=context)[product.id]
                        new_std_price = (
                            (amount_unit * product.qty_available) + (
                                new_price * qty)) / (
                                    product.qty_available + qty)

                    product_obj.write(cr, uid, [product.id], {
                        'standard_price': new_std_price})

                    # Record the values that were chosen in the wizard, so they can be
                    # used for inventory valuation if real-time valuation is enabled.
                    self.write(cr, uid, [move.id], {
                        'price_unit': product_price,
                        'price_currency_id': product_currency,
                        })

        for move in too_few:
            product_qty = move_product_qty[move.id]
            if product_qty != 0:
                defaults = {
                    'product_qty' : product_qty,
                    'product_uos_qty': product_qty,
                    'picking_id' : move.picking_id.id,
                    'state': 'assigned',
                    'move_dest_id': False,
                    'price_unit': move.price_unit,
                    }
                prodlot_id = prodlot_ids[move.id]
                if prodlot_id:
                    defaults.update(prodlot_id=prodlot_id)
                new_move = self.copy(cr, uid, move.id, defaults)
                complete.append(self.browse(cr, uid, new_move))
            self.write(cr, uid, [move.id], {
                'product_qty': move.product_qty - product_qty,
                'product_uos_qty': move.product_qty - product_qty,
                'prodlot_id': False,
                'tracking_id': False,
                })

        for move in too_many:
            self.write(cr, uid, [move.id], {
                'product_qty': move.product_qty,
                'product_uos_qty': move.product_qty,
                })
            complete.append(move)

        for move in complete:
            if prodlot_ids.get(move.id):
                self.write(cr, uid, [move.id], {
                    'prodlot_id': prodlot_ids.get(move.id)})
            self.action_done(cr, uid, [move.id], context=context)
            if  move.picking_id.id :
                # TOCHECK : Done picking if all moves are done
                cr.execute("""
                    SELECT move.id FROM stock_picking pick
                    RIGHT JOIN 
                        stock_move move ON move.picking_id = pick.id AND 
                        move.state = %s
                    WHERE pick.id = %s""",
                        ('done', move.picking_id.id))
                res = cr.fetchall()
                if len(res) == len(move.picking_id.move_lines):
                    picking_obj.action_move(
                        cr, uid, [move.picking_id.id])
                    wf_service.trg_validate(
                        uid, 'stock.picking', move.picking_id.id, 
                        'button_done', cr)

        return [move.id for move in complete]
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
