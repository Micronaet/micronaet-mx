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


        
class report_webkit_html(report_sxw.rml_parse):    
    def __init__(self, cr, uid, name, context):
        ''' Instantiate report obj:
        '''
        super(report_webkit_html, self).__init__(
            cr, uid, name, context=context)
            
        self.localcontext.update({
            'time': time,
            'cr': cr,
            'uid': uid,
            'start_up': self._start_up,
            'get_rows': self._get_rows,
            'get_cols': self._get_cols,
            'get_cel': self._get_cel,
            'jump_is_all_zero': self._jump_is_all_zero,
            })

    def _start_up(self, data=None):
        ''' Call startup procedure
        '''
        return self.pool.get('mrp.production')._start_up(data=data)

    def _get_rows(self):
        ''' Rows list (generated by _start_up function)
        '''
        return self.pool.get('mrp.production')._get_rows()

    def _get_cols(self):
        ''' Cols list (generated by _start_up function)
        '''
        return self.pool.get('mrp.production')._get_cols()

    def _get_cel(self, col, row):
        ''' Get cell
        '''
        return self.pool.get('mrp.production')._get_cel(col, row)

    def _jump_is_all_zero(self, row, data=None):
        ''' Test if line has all elements = 0 
            Response according with wizard filter
        '''        
        return self.pool.get('mrp.production')._jump_is_all_zero(
            row, data=data)

report_sxw.report_sxw(
    'report.webkitstatus',
    'sale.order', 
    'addons/production_line/report/status_webkit.mako',
    parser=report_webkit_html
    )
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
