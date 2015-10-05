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

from openerp.osv import fields, osv, orm
from datetime import datetime
from openerp.tools.translate import _
import os

class ResPartnerAgentCommissionWizard(osv.osv_memory):
    ''' Wizard pre commission report
    '''
    _name = 'res.partner.agent.commission.wizard'

    # Button event:
    def action_open_report(self, cr, uid, ids, context=None):
        ''' Open report
        '''
        if context is None: 
            context = {}

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        data = {}
        data['user_id'] = wiz_proxy.user_id.id
        data['from_date'] = wiz_proxy.from_date
        data['to_date'] = wiz_proxy.to_date

        return {
            'type': 'ir.actions.report.xml', 
            'report_name': 'commission_report',        
            'datas': data,
            }

    _columns = {
        'user_id': fields.many2one('res.users', 'Agent', 
            domain=[('is_agent', '=', True)]),
        'from_date': fields.date('Date from'),
        'to_date': fields.date('Date to'),
        }

    _defaults = {
        #'to_date': lambda *x: 
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
