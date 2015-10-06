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
from datetime import datetime
from openerp.tools.translate import _
import os

class mrp_print_lavoration_week__wizard(osv.osv_memory):
    ''' Wizard that let choose week and print the list of lavorations
    '''
    _name = "mrp.print.lavoration.week.wizard"

    # On Change event:
    def onchange_reference_date(self, cr, uid, ids, reference_date, 
            context=None):
        ''' Compute from date to date and week
        '''
        res = {}
        res['value'] = {}
        res['value']['week'] = self.default_date_from_to(
            cr, uid, 'week', reference_date, context=context)
        res['value']['from_date'] = self.default_date_from_to(
            cr, uid, 'from_date', reference_date, context=context)
        res['value']['to_date'] = self.default_date_from_to(
            cr, uid, 'to_date', reference_date, context=context)
        return res
        
    # Wizard button:
    def action_print_lavoration_week(self, cr, uid, ids, context=None):
        ''' Create new lavoration and recompute actual materials according to 
            quantity to produce
        '''
        if context is None: 
            context = {}
        
        wizard_browse = self.browse(cr, uid, ids, context=context)[0]         
        datas = {}
        if wizard_browse.workcenter_ids:
            datas['workcenter_ids'] = [
                item.id for item in wizard_browse.workcenter_ids]
        datas['from_date'] = self.default_date_from_to(
            cr, uid, 'from_date', wizard_browse.date, context=context)
        datas['week'] = self.default_date_from_to(
            cr, uid, 'week', wizard_browse.date, context=context)
        datas['to_date'] = self.default_date_from_to(
            cr, uid, 'to_date', wizard_browse.date, context=context)
        datas['extended'] = wizard_browse.extended
        datas['only_open'] = wizard_browse.only_open

        return { # action report
                'type': 'ir.actions.report.xml',
                'report_name': "lavoration_weekly_planner_report",
                'datas': datas,
            }            

    # default function:        
    def default_date_from_to(self, cr, uid, data_type, reference_date=False, 
            context=None):
        ''' Get default value for 4 type of data:
        '''        
        import datetime
        from dateutil.relativedelta import relativedelta
        
        if reference_date:
            ref = datetime.datetime.strptime(reference_date, "%Y-%m-%d")
        else:
            ref = datetime.date.today()
        iso_info = ref.isocalendar()

        if data_type == 'date':
            return ref.strftime("%Y-%m-%d")
        elif data_type == 'from_date':
            return (ref + relativedelta(
                days = -(iso_info[2] -1))).strftime("%Y-%m-%d")
        elif data_type == 'to_date':
            return (ref + relativedelta(
                days=7 - iso_info[2])).strftime("%Y-%m-%d")
        elif data_type == 'week':
            return iso_info[1] # week of a year
        else: 
            return False # not possible

    _columns = {
        'date': fields.date('Reference date', 
            help='Reference date for get week information', required=True),
        'from_date': fields.date('Date from'),
        'to_date': fields.date('Date to'),
        'week': fields.integer('Week of the year',),
        'extended': fields.boolean('Extended', 
            help="Extended week (from monday to sunday, else from monday to friday)"),
        'only_open': fields.boolean('Only open', 
            help="Print lavoration open, for all uncheck the value"),
        'workcenter_id':fields.many2one('mrp.workcenter', 'Workcenter', 
            help="No selection is for all workcenter used in the range of dates"),
        'workcenter_ids':fields.many2many('mrp.workcenter', 
            'planner_workcenter_rel', 'wizard_id', 'workcenter_id', 
            'Workcenters'),
        }
        
    _defaults = {
        'date': lambda s, cr, uid, c: s.default_date_from_to(cr, uid, 'date', 
            context=c),
        'from_date': lambda s, cr, uid, c: s.default_date_from_to(cr, uid, 
            'from_date', context=c),
        'to_date': lambda s, cr, uid, c: s.default_date_from_to(cr, uid, 
            'to_date', context=c),
        'week': lambda s, cr, uid, c: s.default_date_from_to(cr, uid, 'week', 
            context=c),
        'extended': lambda *x: False,
        'only_open': lambda *x: True,
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
