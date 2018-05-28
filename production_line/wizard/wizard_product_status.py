# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) 
#    
##############################################################################
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
import os
import sys
import logging
import openerp
import xlsxwriter
from openerp.osv import fields, osv, expression
from datetime import datetime, timedelta
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


# WIZARD PRINT REPORT ########################################################
class product_status_wizard(osv.osv_memory):
    ''' Parameter for product status per day
    '''    
    _name = 'product.status.wizard'
    _description = 'Product status wizard'

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def prepare_data(self, cr, uid, ids, context=None):
        ''' Prepare data dict
        '''
        wiz_proxy = self.browse(cr, uid, ids)[0]
        datas = {}
        if wiz_proxy.days:
            datas['days'] = wiz_proxy.days

        datas['active'] = wiz_proxy.active
        datas['negative'] = wiz_proxy.negative
        datas['with_medium'] = wiz_proxy.with_medium
        datas['month_window'] = wiz_proxy.month_window
        return datas

    # -------------------------------------------------------------------------
    # Button events:
    # -------------------------------------------------------------------------
    def export_excel(self, cr, uid, ids, context=None):
        ''' Export excel file
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def write_xls_mrp_line(WS, row, line):
            ''' Write line in excel file
            '''
            col = 0
            for item in line:
                WS.write(row, col, item)
                col += 1
            return True
            
        data = self.prepare_data(cr, uid, ids, context=context)

        # ---------------------------------------------------------------------
        # XLS file:
        # ---------------------------------------------------------------------
        filename = '~/production_status.xlsx'
        filename = os.path.expanduser(filename)
        
        # Open file and write header
        WB = xlsxwriter.Workbook(filename)
        WS = WB.add_worksheet('Material')
        # WS.write(0, 0, 'Codice')

        # ---------------------------------------------------------------------
        # Format elements:
        # ---------------------------------------------------------------------
        format_header = WB.add_format({
            'bold': True, 
            'font_name': 'Arial',
            'font_size': 11,
            })

        format_title = WB.add_format({
            'bold': True, 
            'font_color': 'black',
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'center',
            'valign': 'center',
            'bg_color': 'gray',
            'border': 1,
            })

        format_hidden = WB.add_format({
            'font_color': 'white',
            'font_name': 'Arial',
            'font_size': 8,
            })

        format_data_text = WB.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            })

        format_data_number = WB.add_format({
            'font_name': 'Arial',
            'font_size': 10,
            'align': 'right',
            })

        # ---------------------------------------------------------------------
        # Format columns:
        # ---------------------------------------------------------------------
        # Column dimension:
        #WS.set_column ('A:A', 0, None, {'hidden': 1}) # ID column        
        WS.set_column ('A:A', 30) # Image colums
            
        # Generate report for export:
        context['lang'] = 'it_IT'
        self.start_up(data)
        start_product = False
        
        # Start loop for design table for product and material status:
        # Header: 
        header = [_('Material')]        
        for col in self.get_cols():
            header.append(col)
        write_xls_mrp_line(WS, 0, header)
        
        # Body:
        i = 1 # row position (before 0)
        rows = self.get_rows()
        for row in rows:
            if not self.jump_is_all_zero(row[1], data):
                if not start_product and row[0][0] == 'P':
                    i += 1 # jump one line
                    start_product = True
                    header[0] = _('Product')
                    write_xls_mrp_line(WS, i, header)
                status_line = 0.0
                
                body = [row[0].split(": ")[1]]
                j = 0
                for col in self.get_cols():
                    (q, minimum) = self.get_cel(j, row[1])
                    j += 1
                    status_line += q
                    body.append(status_line)
                    
                    # Choose the color setup:
                    if not status_line: # value = 0
                        pass # White
                    elif status_line > minimum: # > minimum value (green)
                        pass # Green
                    elif status_line > 0.0: # under minimum (yellow)
                        pass # Yellow
                    elif status_line < 0.0: # under 0 (red)
                        pass# Red
                    else: # ("=", "<"): # not present!!!
                        pass # Error!
                write_xls_mrp_line(WS, i, body)
                i += 1                
        return True
        
    def print_report(self, cr, uid, ids, context=None):
        ''' Redirect to bom report passing parameters
        ''' 
        datas = self.prepare_data(cr, uid, ids, context=context)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'webkitstatus',
            'datas': datas,
            }
        
    _columns = {
        'days':fields.integer('Days from today', required=True),
        'active':fields.boolean('Only record with data', required=False, 
            help="Show only product and material with movement"),
        'negative': fields.boolean('Only negative', required=False, 
            help="Show only product and material with negative value in range"),
        'month_window':fields.integer('Statistic production window ', 
            required=True, help="Month back for medium production monthly index (Kg / month of prime material)"),
        'with_medium': fields.boolean('With m(x)', required=False, 
            help="if check in report there's production m(x), if not check report is more fast"),        
        }
        
    _defaults = {
        'days': lambda *a: 7,
        'active': lambda *a: False,
        'negative': lambda *a: False,
        'month_window': lambda *x: 2,
        'with_medium': lambda *x: True,
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
