# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2009-2011 company (http://sitename) All Rights Reserved.
#                    General contacts <author.name@company.com>
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
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
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

{
    'name': 'Production on import sale order',
    'version': '0.1',
    'category': 'Statistic',
    'description': """ Production manage with imported order lines""",
    'author': 'Micronaet s.r.l.',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base', 
        'sale', 
        'account',
        'mrp',
        'mail',
        'stock',
        'knowledge',
        'report_aeroo',
        'report_aeroo_ooo',
        'mrp_operations',
        'base_mssql',
        'base_mssql_accounting',
        'partner_addresses',
        'base_log_scheduler',        
        ],
    'init_xml': [],
    'demo_xml': [],
    'update_xml': [
        'security/visibility_group.xml',
        'security/ir.model.access.csv',                     
        'wizard/confirm_production_wizard.xml',
        'wizard/split_lavoration_wizard.xml',
        'wizard/assign_production.xml',
        'wizard/print_lavoration_week.xml',
        'wizard/print_covered_report.xml',

        'company.xml',
        'product_view.xml',
        'production_view.xml',
        'partner_view.xml',
        'analysis.xml',

        'scheduler.xml',
        'wizard/view_production_wizard.xml',
        'wizard/wizard_product_status_view.xml',
        'workflow/mrp_production_workflow.xml',
        
        'report/status_webkit.xml',
        'report/lavoration_report.xml',
        'report/workcenter_lavoration.xml',
        'report/order_covered.xml',
        'report/bom_report.xml',
        
        'data/template.xml',
        
        'counter.xml',
        ],
    'active': False,
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
