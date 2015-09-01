# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP module
#    Copyright (C) 2010 Micronaet srl (<http://www.micronaet.it>) and the
#    Italian OpenERP Community (<http://www.openerp-italia.com>)
#
#    ########################################################################
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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

from openerp.osv import fields,osv
import os

class sale_order_line_covered_wizard(osv.osv_memory):
    ''' Wizard that assign lavoration to the selected order line
    '''
    _name = "sale.order.line.covered.wizard"
    _description = "Open covered report"

    # Wizard button:
    def action_open_report(self, cr, uid, ids, context=None):
        ''' Open report
        '''
        if context is None: context={}        
        data = {}
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        data['report_type'] = wiz_proxy.type
        
        return {
               'type': 'ir.actions.report.xml', 
               'report_name':'order_covered',        
               'datas': data,
               }
               
    _columns = {
        'type':fields.selection([
            ('line','Only covered lines'),
            ('order','Only covered order'),            
        ],'type', select=True, readonly=False),
    }           
    
    _defaults = {
        'type': lambda *a: 'order',
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


