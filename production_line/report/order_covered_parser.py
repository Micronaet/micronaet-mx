# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008-2011 Alistek Ltd (http://www.alistek.com) All Rights Reserved.
#                    General contacts <info@alistek.com>
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

break_level = False

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,    
            'is_break_level': self.is_break_level,
            'reset_break_level': self.reset_break_level,
            'get_header': self.get_header,
        })

    def get_header(self, data = None):
        ''' Return header depend on wizard filter
        '''
        if data is None:
            data = {}
            
        if data.get('report_type', 'order') == 'order':  # all order covered
            return "Ordini coperti interamente da magazzino"
        else:
            return "Righe ordine coperte da magazzino"
        
    def reset_break_level(self,):
        ''' Reset field that test break level
        '''
        global break_level
        break_level = False

    def is_break_level(self, value):
        ''' Used in report print for test last value and return if the value is
            change, after this new value is saved
        '''
        global break_level
        if value == break_level:
            return False
        else: 
            break_level = value # save actual
            return True                
        
    def get_objects(self, data = None):
        ''' Generate correct record list for print
        '''
        if data is None:
            data = {}
        line_pool = self.pool.get('sale.order.line')
        if data.get('report_type','order')== 'order':  # all order covered
            order_pool = self.pool.get('sale.order')
            order_ids = order_pool.search(self.cr, self.uid, [('accounting_order','=',True)]) # read all order from accounting            
            line_not_covered_ids = line_pool.search(self.cr, self.uid, [('use_accounting_qty','=',False)]) 
            for line in line_pool.browse(self.cr, self.uid, line_not_covered_ids):
                if line.order_id.id in order_ids:
                    order_ids.remove(line.order_id.id) # remove order 
            line_ids = line_pool.search(self.cr, self.uid, [('order_id','in', order_ids)], order='order_id,sequence') 
        else:                                          # lines covered
            line_ids = line_pool.search(self.cr, self.uid, [('use_accounting_qty','=',True)], order='order_id,sequence') # orders?
            
        return line_pool.browse(self.cr, self.uid, line_ids)

