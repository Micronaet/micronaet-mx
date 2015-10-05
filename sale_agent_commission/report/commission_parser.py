#|/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008-2011 Alistek Ltd (http://www.alistek.com) 
# All Rights Reserved. General contacts <info@alistek.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This module is GPLv3 or newer and incompatible
# with OpenERP SA "AGPL + Private Use License"!
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse


class Parser(report_sxw.rml_parse):
    counters = {} # total counters

    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
            'set_counter': self.set_counter,
            'get_counter': self.get_counter,
            'add_counter': self.add_counter,
        })

    def get_counter(self, name):
        ''' Return value of passed counter, if empty create with 0 value
        '''
        if name not in self.counters:
            self.counters[name] = 0.0        
        return self.counters[name]

    def set_counter(self, name, value, with_return=False):
        ''' Set up counter with name passed with the value
            if with return the method return setted value
        '''
        self.counters[name] = value 
        if with_return:
            return self.counters[name]
        else:    
            return '' # Write nothing (not False)

    def add_counter(self, name, value, with_return=False):
        ''' Add counter value and return
        '''
        if name in self.counters:
           self.counters[name] += value
        else:
           self.counters[name] = value
               
        if with_return:
            return value
        else:    
            return ''

    def get_objects(self, data=None):
        ''' Create object for print report
        '''
        
        if data is None:
            data = {}

        res = {}
        order_pool = self.pool.get('sale.order')

        # Create domain filter:
        # Only order:
        domain = [('state', 'not in', ('draft', 'sent', 'cancel'))]
        if data.get('from_date', False):
            domain.append(('date_order', '>=', data.get('from_date', False)))

        if data.get('to_date', False):
            domain.append(('date_order', '<', data.get('to_date', False)))

        if data.get('user_id', False):
            domain.append(('user_id', '=', data.get('user_id', False)))

        order_ids = order_pool.search(self.cr, self.uid, domain)
        for order in order_pool.browse(self.cr, self.uid, order_ids):
            if order.user_id not in res:
                res[order.user_id] = []
                
            for detail in order.order_line:
                # append all rows:
                res[order.user_id].append(detail)
        return res         
