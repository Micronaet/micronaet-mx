# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) 
#    
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import sys
import os
from openerp.osv import osv
from datetime import datetime, timedelta
from openerp.report import report_sxw
import time, logging
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, float_compare)

# global value:
_logger = logging.getLogger(__name__)
rows = []
cols = []
minimum = {}
table = {}
error_in_print = ''

class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    
    _inherit = 'mrp.production'
    
    # -------------------------------------------------------------------------
    # Utility function:
    # -------------------------------------------------------------------------
    def _jump_is_all_zero(self, row, data=None):
        ''' Test if line has all elements = 0 
            Response according with wizard filter
        '''
        if data is None:
            data = {}

        global table
            
        if data.get('active', False):  # only active lines?
            return not any(table[row]) # jump line (True)
        return False # write line

    def _start_up(self, data=None):
        ''' Master function for prepare report
        '''
        # Utility:
        #def format_element(product, rows):            
        
        # Readability:
        cr = self.cr
        uid = self.uid
        context = {}

        if data is None:
            data = {}

        # Pool used:
        accounting_pool = self.pool.get('micronaet.accounting')
        lavoration_pool = self.pool.get('mrp.production.workcenter.line')
        product_pool = self.pool.get('product.product')
        
        # Global parameters:    
        global rows, cols, table, minimum, error_in_print
        
        # initialize globals:
        rows = []
        cols = []
        minimum = {}
        table = {}
        error_in_print = '' # TODO manage for set in printer
        
        # TODO optimize:
        product_ids = product_pool.search(cr, uid, [], context=context)
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            minimum[product.id] = product.minimum_qty or 0.0

        # Init parameters:      
        col_ids = {}  
        range_date = data.get('days', 7) + 1
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days = range_date - 1)

        # 0 (<today), 1..n [today, today + total days], delta)
        for i in range(0, range_date): 
            if i == 0: # today
                d = start_date
                cols.append(d.strftime('%d/%m'))
                col_ids[d.strftime('%Y-%m-%d')] = 0
            elif i == 1: # before today
                d = start_date
                cols.append(d.strftime('< %d/%m')) 
                col_ids['before'] = 1 # not used!                    
            else: # other days
                d = start_date + timedelta(days = i - 1)
                cols.append(d.strftime('%d/%m'))
                col_ids[d.strftime('%Y-%m-%d')] = i

        # ---------------------------------------------------------------------
        #                     SYNCRONIZATION PRE REPORT
        # ---------------------------------------------------------------------
        # --------------------------------------
        # 1. Import status material and product:
        # --------------------------------------
        
        
        # ------------------------------
        # 2. Get OF lines with deadline:
        # ------------------------------
        supplier_orders = {}
        # TODO Filter period?? (optimizing the query!)
        cursor_of = accounting_pool.get_of_line_quantity_deadline(cr, uid)
        if not cursor_of: 
            _logger.error(
                'Error access OF line table in accounting! (status webkit)')
        else:
            for supplier_order in cursor_of: # all open OC
                ref = supplier_order['CKY_ART'].strip()
                if ref not in supplier_orders:
                    supplier_orders[ref] = {}
                # TODO verify if not present
                of_deadline = supplier_order['DTT_SCAD'].strftime('%Y-%m-%d') 

                q = float(supplier_order['NQT_RIGA_O_PLOR'] or 0.0) * (
                    1.0 / supplier_order['NCF_CONV'] \
                        if supplier_order['NCF_CONV'] else 1.0)
                if of_deadline not in supplier_orders[ref]: # TODO test UM
                    supplier_orders[ref][of_deadline] = q 
                else:
                    supplier_orders[ref][of_deadline] += q

        # -------------------
        # 3. Get OC elements:
        # -------------------

        # ---------------------------
        # 4. Get m(x) for production:
        # ---------------------------
        material_mx = {}
        with_medium = data.get('with_medium', False)
        month_window = data.get('month_window', 2)
        if with_medium:            
            from_date = (datetime.now() - timedelta(
                days=30 * month_window)).strftime(
                    DEFAULT_SERVER_DATETIME_FORMAT)
            lavoration_material_ids = lavoration_pool.search(cr, uid, [
                ('real_date_planned', '>=', from_date),
                ('state', 'in', ('done', 'startworking')),
                ], context=context)
            for lavoration in lavoration_pool.browse(
                    cr, uid, lavoration_material_ids, context=context):
                for material in lavoration.bom_material_ids:
                    product = material.product_id # Readability:
                    if product.id in material_mx:
                        material_mx[product.id] += \
                            material.quantity or 0.0
                    else:
                        material_mx[product.id] = \
                            material.quantity or 0.0

        # ---------------------------------------------------------------------
        #                       GENERATE HEADER VALUES
        # ---------------------------------------------------------------------
        # -------------------------------
        # Get product list from OC lines:
        # -------------------------------
        # > populate cols 
        order_line_pool = self.pool.get('sale.order.line')
        
        line_ids = order_line_pool.search(cr, uid, [
            ('date_deadline', '<=', end_date.strftime('%Y-%m-%d')),
            ], context=context) # only active from accounting
        for line in order_line_pool.browse(cr, uid, line_ids, context=context):
            if line.product_id.not_in_status: # jump line
                continue
            element = ('P: %s [%s]' % (
                line.product_id.name, 
                line.product_id.default_code, 
                ), 
                line.product_id.id,
                )
            # initialize row (today, < today, +1, +2, ... +n)                
            if element not in rows: 
                rows.append(element)
                
                # prepare data structure
                table[element[1]] = [0.0 for item in range(0, range_date)]
                 
                # start q.
                table[element[1]][0] = line.product_id.accounting_qty or 0.0 
                        
            if line.order_id.date_deadline in col_ids: # all date
                table[element[1]][col_ids[line.order_id.date_deadline]] -= \
                    line.product_uom_qty or 0.0  # OC deadlined this date    
            if not line.order_id.date_deadline or \
                    line.order_id.date_deadline < start_date.strftime(
                        '%Y-%m-%d'): # only < today
                # OC deadlined before today:        
                table[element[1]][1] -= line.product_uom_qty or 0.0

        # ---------------------------------------------------------------------
        #                   Get material list from Lavoration order
        # ---------------------------------------------------------------------
        # Populate cols:
        lavoration_ids = lavoration_pool.search(cr, uid, [
            # only < max date range
            ('real_date_planned', '<=', end_date.strftime(
                '%Y-%m-%d 23:59:59')),     
            ('state', 'not in', ('cancel','done')),
            ], context=context) # only open not canceled
        for lavoration in lavoration_pool.browse(
                cr, uid, lavoration_ids, context=context): # filtered BL orders
                
            # ----------------------------
            # Product in lavoration order:
            # ----------------------------
            element = ('P: %s [%s]' % (
                lavoration.product.name, 
                lavoration.product.code,
            ), lavoration.product.id)

            if element not in rows:
                # prepare data structure:
                rows.append(element)            
                table[element[1]] = [0.0 for item in range(0, range_date)]       
                table[element[1]][0] = lavoration.product.accounting_qty or 0.0

            # Product production:
            if lavoration.real_date_planned[:10] in col_ids: 
                table[element[1]][
                    col_ids[lavoration.real_date_planned[:10]]] += \
                        lavoration.product_qty or 0.0
            else: # < today  (element 1 - the second)
                table[element[1]][1] += lavoration.product_qty or 0.0

            # ----------------
            # Material in BOM:
            # ----------------                  
            for material in lavoration.bom_material_ids:     
                # Readability:
                product = material.product_id
                default_code = product.default_code
                
                if product.not_in_status: # Jump 'not in status' material
                    continue

                if with_medium and product:
                    # t from Kg.
                    media = '%5.2f' % (
                        material_mx.get(product.id, 0.0) / month_window / 1000) 
                else:
                    media = '??'

                element=('M: %s [%s]%s' % (
                    product.name, 
                    default_code,
                    ' <b>%s t.</b>' % (media), ), product.id)
                if element not in rows:
                    rows.append(element)
                    # prepare data structure:
                    table[element[1]] = [0.0 for item in range(0,range_date)] 
                    # prepare data structure:
                    table[element[1]][0] = product.accounting_qty or 0.0 

                if lavoration.real_date_planned[:10] in col_ids:
                    table[element[1]][col_ids[
                        lavoration.real_date_planned[:10]]] -= \
                            material.quantity or 0.0 
                else:    # < today
                    table[element[1]][1] -= material.quantity or 0.0 

                # ---------
                # OF order:
                # ---------                
                if default_code in supplier_orders: # all OF orders
                    for of_deadline in supplier_orders[default_code].keys():
                        # deadline is present in the window of cols
                        if of_deadline in col_ids:                            
                            table[element[1]][col_ids[of_deadline]] += \
                                supplier_orders[default_code][of_deadline] or \
                                    0.0
                            # delete OF value (no other additions):        
                            del(supplier_orders[default_code][of_deadline]) 
                            
                        elif of_deadline < start_date.strftime('%Y-%m-%d'):
                            # deadline < today:   
                            table[element[1]][1] += supplier_orders[
                                default_code][of_deadline] or 0.0
                            # delete OF value (no other additions):
                            del(supplier_orders[default_code][of_deadline]) 
        rows.sort()

        # -----------------------
        # Generation table data: 
        # -----------------------
        # > Setup initial value:
        # > Import -q for material in lavoration:
        # > Import +q for product in lavoration:
        # > Import OC product in line with deadline:
        # > Import OF material with deadline:
        return True
        
class report_webkit_html(report_sxw.rml_parse):    
    def __init__(self, cr, uid, name, context):
        super(report_webkit_html, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'time': time,
            'cr': cr,
            'uid': uid,
            'start_up': self._start_up,
            'get_rows': self._get_rows,
            'get_cols': self._get_cols,
            'get_cel': self._get_cel,
            #'has_negative': self._has_negative,
            'jump_is_all_zero': self._jump_is_all_zero,
        })

    def _jump_is_all_zero(self, row, data=None):
        ''' Test if line has all elements = 0 
            Response according with wizard filter
        '''        
        return self.pool.get('mrp.production')._jump_is_all_zero(
            row, data=data)

    def _start_up(self, data=None):
        ''' Call startup procedure
        '''
        return self.pool.get('mrp.production')._start_up(data=data)

    def _get_rows(self):
        ''' Rows list (generated by _start_up function)
        '''
        # Global parameters:    
        global rows
        return rows

    def _get_cols(self):
        ''' Cols list (generated by _start_up function)
        '''
        # Global parameters:    
        global cols
        return cols

    def _get_cel(self, col, row):
        ''' Cel value from col - row
            row=product_id
            col=n position
            return: (quantity, minimum value)
        '''
        # Global parameters:    
        global table
        global minimum
        
        # TODO get from table
        if row in table:
            return (table[row][col], minimum.get(row, 0.0))
        return (0.0, 0.0)

report_sxw.report_sxw(
    'report.webkitstatus',
    'sale.order', 
    'addons/production_line/report/status_webkit.mako',
    parser=report_webkit_html
)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
