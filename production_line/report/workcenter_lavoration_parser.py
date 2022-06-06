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

lavoration_objects = {}
days_objects = []
no_page_break = False
total_per_day_line = {}

class Parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_lines': self.get_lines,
            'get_objects': self.get_objects,
            'get_days': self.get_days,
            'get_no_page_break': self.get_no_page_break,
            'format_7_days': self.format_7_days,
            'get_total_per_day_line': self.get_total_per_day_line,
        })

    def get_total_per_day_line(self):
        """ Return total obj per day per line
        """
        global total_per_day_line
        return total_per_day_line

    def format_7_days(self, datas=None):
        """ If extended parameter is passed, the format is 7 days
        """
        if datas is None:
            datas = {}
        return datas.get('extended', False)

    def get_no_page_break(self, datas=None):
        """ Number of records (for page break)
        """
        global no_page_break
        return no_page_break

    def get_days(self, datas=None):
        """ Return days obj (calculated in get_lines)
        """
        global days_objects
        return days_objects

    def get_objects(self, datas=None):
        """ Return master obj (calculated in get_lines)
        """
        global lavoration_objects
        return lavoration_objects

    def get_lines(self, datas=None):
        """ Load browse object for master list
        """
        import datetime
        from dateutil.relativedelta import relativedelta

        global lavoration_objects, days_objects, no_page_break, total_per_day_line

        # Init global object
        lavoration_objects = {}
        days_objects = []
        no_page_break = False
        total_per_day_line = {}

        domain = []

        if datas is None:
            return lavoration_objects # no report

        from_date = datas.get('from_date', False)
        to_date = datas.get('to_date', False)
        workcenter_ids = datas.get('workcenter_ids', False)

        if not (from_date and to_date):
            return lavoration_objects # no report

        # --------------------------------------------
        # compose days list (fro report visualization)
        # --------------------------------------------
        date_ref = datetime.datetime.strptime(from_date, "%Y-%m-%d")
        for seq in range(0,7): # from 0 to 6
            days_objects.append((date_ref + relativedelta(days = seq)).strftime("%d-%m"))

        domain.extend([('real_date_planned','>=',"%s 00:00:00"%(from_date)),('real_date_planned','<=',"%s 23:59:59"%(to_date)),('state','!=','cancel')])

        if workcenter_ids:
            domain.append(('workcenter_id','in',workcenter_ids))
            no_page_break = True  # if selected more than one line, no page break

        if datas.get('only_open', False): # filter only open lavoration
            domain.append(('state','!=','done'))

        lavoration_ids = self.pool.get('mrp.production.workcenter.line').search(self.cr, self.uid, domain, order='real_date_planned')
        if not lavoration_ids:
            return lavoration_objects # no report

        for lavoration in self.pool.get('mrp.production.workcenter.line').browse(self.cr, self.uid, lavoration_ids):
            if lavoration.workcenter_id.name not in lavoration_objects:
                # start daily list:            Mo,Tu,We,Th,Fr,Sa,Su
                #                               0  1  2  3  4  5  6
                #lavoration_objects[lavoration.workcenter_id]=[[],[],[],[],[],[],[]]
                lavoration_objects[lavoration.workcenter_id.name]=[[],[],[],[],[],[],[]]

            position = (datetime.datetime.strptime(lavoration.real_date_planned[:10], "%Y-%m-%d")).isocalendar()[2] -1
            lavoration_objects[lavoration.workcenter_id.name][position].append(lavoration)

            # Update totals:
            if (lavoration.workcenter_id.name, position) not in total_per_day_line:
                total_per_day_line[(lavoration.workcenter_id.name, position)] = [0.0, 0.0]
            total_per_day_line[(lavoration.workcenter_id.name, position)][0] += lavoration.single_cycle_duration *  lavoration.cycle # Hours
            total_per_day_line[(lavoration.workcenter_id.name, position)][1] += lavoration.single_cycle_qty *  lavoration.cycle      # Qty
        return lavoration_objects

