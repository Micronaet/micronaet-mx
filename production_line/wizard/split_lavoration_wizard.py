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
import os
import sys
from openerp.osv import fields,osv
from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _


class mrp_production_split_wizard(osv.osv_memory):
    ''' Wizard that split lavoration removing some cycle
    '''
    _name = "mrp.production.split.wizard"

    # On Change event:
    def onchange_split_daily(self, cr, uid, ids, split_daily, context=None):
        ''' Test if split daily return a list of lavoration that will be created
        '''
        res = {}
        
        if context is None:
            res['value'] = {'split_daily_note': 'Unable to calculate split values, context not present!',}
        

        lavoration_proxy = self.pool.get("mrp.production.workcenter.line").browse(cr, uid, context.get('active_id',0), context=context)
        working_hour_day = lavoration_proxy.workcenter_id.hour_daily_work if lavoration_proxy.workcenter_id else 16 #(default)
        if lavoration_proxy and split_daily:        
            current_start = datetime.strptime(lavoration_proxy.real_date_planned[:10], "%Y-%m-%d")
            daily_cycle = int(working_hour_day // lavoration_proxy.single_cycle_duration)
            if not daily_cycle:
                raise osv.except_osv(
                    _('Error'), 
                    _('No Working hour for line or single cycle duration!'),
                    )
            remain = int(lavoration_proxy.cycle % daily_cycle)
            split_days = int(lavoration_proxy.cycle // daily_cycle + (1 if remain > 0 else 0))
            #split_days = daily_cycle + (1 if remain > 0 else 0)
            note = _("Split lavoration plan (max %s cycle a day):") % (daily_cycle)            
            current_date = current_start
            for i in range(0, split_days):
                if current_date.isocalendar()[2] == 7:   # Sunday
                    current_date = current_date + relativedelta(days = 1)
                elif current_date.isocalendar()[2] == 6: # Monday
                    current_date = current_date + relativedelta(days = 2)
                cycle = remain if remain > 0 and i + 1 == split_days else daily_cycle
                date = current_date.strftime("%Y-%m-%d")
                note += _('\n%s \tcycle: %s \tH: %s [Tot.: %s] - \tQ.: %s [Tot.: %s]') % (
                    "%s-%s" % (date[8:10], date[5:7]),               # Date
                    cycle,                                           # Cycle a day

                    lavoration_proxy.single_cycle_duration,          # Tot duration per lavoration
                    cycle * lavoration_proxy.single_cycle_duration,  # Tot duration per day                                                                                   

                    lavoration_proxy.single_cycle_qty,               # Tot Q. per lavoration
                    cycle * lavoration_proxy.single_cycle_qty,       # Tot Q. per day                                                                                   
                )
                current_date = current_date + relativedelta(days = 1)
            
            res['value'] = {'split_daily_note': note}
        else:             
            res['value'] = {'split_daily_note': ''}
        return res
        
    # Wizard button:
    def action_split_order(self, cr, uid, ids, context=None):
        ''' Create new lavoration and recompute actual materials according to quantity to produce
        '''
        from datetime import datetime
        
        lavoration_pool = self.pool.get("mrp.production.workcenter.line")
        # Utility function:
        def create_lavoration(self, cr, uid, lavoration_proxy, cycle, date_start, sequence, context=None):
            ''' Create a lavoration with passed parameters, according to the one
                used as reference
                lavoration_proxy: reference object for get parameter (default)
                cycle: number of cycle
                date_start: start of new lavoration
                sequence: sequence passed 
                @return: boolean for esit
            '''
            data = {
                #'name': "%sbis"%(lavoration_proxy.name), #u'MO/00011#2', 
                'real_date_planned_end': False, 
                'real_date_planned': date_start, 
                'date_planned': date_start,      

                'cycle': cycle,
                'single_cycle_qty': lavoration_proxy.single_cycle_qty,
                'single_cycle_duration': lavoration_proxy.single_cycle_duration,
                'product_qty': cycle * lavoration_proxy.single_cycle_qty, 
                'hour': cycle * lavoration_proxy.single_cycle_duration,
                  
                'sequence': sequence, 
                'bom_material_ids': False,
                'load_confirmed': False,
                'message_ids': False,
                'real_product_qty': 0.0,
                'date_start': False,
                'delay': 0.0,
                'state': 'draft',
                'lavoration_note': False, 
                'workcenter_id': lavoration_proxy.workcenter_id.id,
                'load_ids': False,
                'date_finished': False,
                'anomalie_note': False,
                'force_cycle_default': False,
                'production_id': lavoration_proxy.production_id.id,
            }
            lavoration_id = lavoration_pool.create(cr, uid, data, context=context)
            lavoration_pool._create_bom_lines(cr, uid, lavoration_id, context=context)
            
        if context is None: 
            context={}                
        # Common part:    
        wizard_browse = self.browse(cr, uid, ids, context=context)[0] # wizard fields proxy
        origin_lavoration_id = context.get("active_id", 0)
        
        lavoration_proxy = lavoration_pool.browse(cr, uid, origin_lavoration_id,context=context)
        
        if not wizard_browse.split_daily: 
            # ---------------------------------
            # Lavoration non completed to split
            # ---------------------------------

            cycle = wizard_browse.cycle_remain
            sequence = lavoration_proxy.sequence + 1
            date_start = wizard_browse.datetime

            if not cycle or cycle >= lavoration_proxy.cycle:
                return {'type':'ir.actions.act_window_close'} # Comunicare l'errore se i cicli sono maggiori 
            create_lavoration(self, cr, uid, lavoration_proxy, cycle, date_start, sequence, context=context)
            first_cycle = lavoration_proxy.cycle - cycle # to update first lavoration element
            
        else:
            # ---------------------------------
            # Lavoration non completed to split
            # ---------------------------------

            current_start = datetime.strptime(lavoration_proxy.real_date_planned[:10], "%Y-%m-%d")
            current_date = current_start + relativedelta(days = 1) # jump first day
            
            working_hour_day = lavoration_proxy.workcenter_id.hour_daily_work if lavoration_proxy.workcenter_id else 16 #(default)
            daily_cycle = int(working_hour_day // lavoration_proxy.single_cycle_duration)   # cycle that I can do per day
            remain = int(lavoration_proxy.cycle % daily_cycle) # last cycle remain (for last day)
            
            split_days = int( lavoration_proxy.cycle // daily_cycle + (1 if remain > 0 else 0))

            if split_days < 2: # TODO fare con debug la verifica per 0 e 1
                return {'type': 'ir.actions.act_window_close'} # Comunicare l'errore se i cicli sono maggiori 

            first_cycle = daily_cycle #if split_days > 1 else remain # to update first lavoration element
            sequence = lavoration_proxy.sequence 

            for i in range(1, split_days): # Jump first day (is update after on ref. lavoration)
                if current_date.isocalendar()[2] == 7:   # Sunday
                    current_date = current_date + relativedelta(days = 1)
                elif current_date.isocalendar()[2] == 6: # Monday
                    current_date = current_date + relativedelta(days = 2)
                    
                sequence = lavoration_proxy.sequence + 1                    
                cycle = remain if remain > 0 and i + 1 == split_days else daily_cycle
                date_start = current_date.strftime("%Y-%m-%d 06:00:00")                
                create_lavoration(self, cr, uid, lavoration_proxy, cycle, date_start, sequence, context=context)                
                current_date = current_date + relativedelta(days = 1)

        # Update origin lavoration:
        update_data = {
            'cycle': first_cycle,
            'product_qty': first_cycle * lavoration_proxy.single_cycle_qty, 
            'hour': first_cycle * lavoration_proxy.single_cycle_duration,
        }
        lavoration_pool.write(cr, uid, [origin_lavoration_id], update_data, context=context)
        lavoration_pool._create_bom_lines(cr, uid, origin_lavoration_id, context=context)
            
        return {'type':'ir.actions.act_window_close'}   # sostituire con l'apertura della nuova lavorazione (vedere se è il caso)

    # default function:        
    def default_quantity(self, cr, uid, context=None):
        ''' Get default value
        '''
        wc_pool = self.pool.get('mrp.production.workcenter.line')
        wc_browse = wc_pool.browse(cr, uid, context.get("active_id", 0), context=context)
        return wc_browse.cycle - 1.0 if wc_browse else 1.0

    _columns = {
        'cycle_remain': fields.integer('Cycle remain', required=False),
        'datetime': fields.datetime('Date next', help='Date next lavoration', required=False),
        'split_daily': fields.boolean('Daily split', help='Is checked this lavoration is splitted depending on working hour'),
        'split_daily_note': fields.text('Daily split note', help='List of all division cycle per day according to hour per line daily'),
    }
        
    _defaults = {
        'cycle_remain': lambda s, cr, uid, c: s.default_quantity(cr, uid, context=c),
        'split_daily': lambda *x: False,
    }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


