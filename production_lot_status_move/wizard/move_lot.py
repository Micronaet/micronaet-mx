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
import openerp.netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class move_lot_wizard(osv.osv_memory):
    ''' Wizard that confirm production/lavoration
    '''
    _name = "stock.production.lot.move.wizard"

    """def get_xmlrpc_server(self, cr, uid, parameter, context=None):
        ''' Configure and retur XML-RPC server for accounting        
        '''
        try:
            mx_parameter_server = parameter.production_host
            mx_parameter_port = parameter.production_port

            xmlrpc_server = "http://%s:%s" % (
                mx_parameter_server,
                mx_parameter_port,
            )
        except:
            raise osv.except_osv(
                _('Import CL error!'),
                _('XMLRPC for calling importation is not response'), )
                
        return xmlrpclib.ServerProxy(xmlrpc_server)"""
        
    # ---------------
    # Onchange event:
    # ---------------
    #def onchange_move_type(self, cr, uid, ids, move_type, from_product_id, context=None):
    #    ''' On change move type set to_product
    #    '''
    #    res = {}
    #    res['value'] = {}
    #    if move_type == 'package':
    #        res['value']['to_product_id'] = from_product_id # same product
    #    return res

    def onchange_from_lot(self, cr, uid, ids, from_lot_id, move_qty, context=None):
        ''' On change move type set to_product
        '''
        res = {}
        res['value'] = {}

        if from_lot_id:
            lot_pool = self.pool.get("stock.production.lot")
            lot_proxy = lot_pool.browse(cr, uid, from_lot_id, context=context)
            if move_qty and move_qty < lot_proxy.stock_available_accounting:
                res['value']['move_qty'] = move_qty
            else:
                res['value']['move_qty'] = lot_proxy.stock_available_accounting
        else:
            res['value']['move_qty'] = 0.0
        return res

    # --------------
    # Wizard button:
    # --------------
    def action_move_lot(self, cr, uid, ids, context=None):
        ''' Create transition file and launch via XML-RPC import procedure
        '''
        if context is None:
            context = {}

        wiz_proxy = self.browse(
            cr, uid, ids, context=context)[0]

        if not wiz_proxy.move_qty:
            raise osv.except_osv(
                _('Empty quantity:'),
                _('Please fill quantity for the stock move!'))

        # XMLRPC server:
        xmlrpc_server = self.pool.get('res.company').xmlrpc_get_server(cr, uid, context=context)
        if not xmlrpc_server:
            raise osv.except_osv(
                _('Accounting connection error:'),
                _('Unable to connect to accounting server, check parameter or'
                  'server state!'))
        
        line = "%10s%16s%10.2f" % (
            wiz_proxy.from_lot_id.ref, # ID lot in accounting
            "XXXXXX%-10s" % wiz_proxy.to_package_id.code if wiz_proxy.to_new_lot else wiz_proxy.to_lot_id.name, # Lot
            wiz_proxy.move_qty,
            )
        
        try:
            error = xmlrpc_server.sprix("MOVE", {'line': line, })
            if error:
                raise osv.except_osv(
                    _('Accounting error:'),
                    _('Error managing movement in accounting!'))
        except:            
            raise osv.except_osv(
                _('XMLRPC error:'),
                _('Error launching procedure!'))

        return {'type':'ir.actions.act_window_close'}

    _columns = {
        'from_product_id': fields.many2one('product.product', 'Product'),
        'from_lot_id': fields.many2one('stock.production.lot', 'From lot', 
            required=True),
        'to_product_id': fields.many2one('product.product', 'To Product'),
        'to_package_id': fields.many2one('product.ul', 'To Package'),
        'to_lot_id': fields.many2one('stock.production.lot', 'To lot'),
        'to_new_lot': fields.boolean('To new lot'),
        'move_qty': fields.float('Move qty', digits=(16, 2), required=True),
        }
    _defaults = {
        'to_new_lot': lambda *x: False,
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
