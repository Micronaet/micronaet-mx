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
import openerp.netsvc as netsvc
import logging
from openerp.osv import osv, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse


_logger = logging.getLogger(__name__)

# Global parameters:
parameters = False

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'load_parameter': self.load_parameter,
            'get_parameter': self.get_parameter,            
            'get_analysis_info': self.get_analysis_info,
        })

    def load_parameter(self, product_id, workcenter_id):
        ''' Load browse object for get parameters
        '''
        global parameters, parameter_loaded
        parameters = False # reset previous value
        
        workcenter_pool = self.pool.get('mrp.workcenter')
        history_pool = self.pool.get('mrp.workcenter.history')        
        if product_id and workcenter_id:
            # test if workcenter is a child:
            workcenter_proxy = workcenter_pool.browse(self.cr, self.uid, workcenter_id)
            if workcenter_proxy.parent_workcenter_id:
                workcenter_id = workcenter_proxy.parent_workcenter_id.id
            
            # Setup browse object
            history_ids = history_pool.search(self.cr, self.uid, [
                ('product_id', '=', product_id),
                ('workcenter_id', '=', workcenter_id)
            ])
            if history_ids:            
                parameters = history_pool.browse(self.cr, self.uid, history_ids)[0]
        return

    def get_parameter(self, name):
        ''' Return parameters browse obj
        '''
        global parameters        
        try:
            return parameters.__getattr__(name) 
        except:
            return ""            
        return parameters

    def get_analysis_info(self, production_id):
        ''' Return specific information for customers that have this order line 
        '''
        production_browse = self.pool.get("mrp.production").browse(self.cr, self.uid, production_id)
        note = {}
       
        for line in production_browse.order_lines_ids:
            if line.partner_id and line.partner_id.analysis_required and line.partner_id.name not in note:
                note[line.partner_id.name] = line.partner_id.analysis_note if line.partner_id.analysis_note else "Analysis mandatory"
                    
        res = ""           
        for key in note:
            res += "[%s] %s\n" % (key, note[key])
        return res
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
