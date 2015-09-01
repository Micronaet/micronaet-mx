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
import xmlrpclib
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class res_company(osv.osv):
    ''' Extra fields for res.company object
    '''
    _name = "res.company"
    _inherit = "res.company"

    def get_production_parameter(self, cr, uid, context=None):
        ''' Return browse object for default company for get all parameter created
        '''
        company_id = self.search(cr, uid, [], context=context)
        if company_id:
            return self.browse(cr, uid, company_id, context=context)[0]
        else:
            return False

    def xmlrpc_get_server(self, cr, uid, context=None):
        ''' Configure and retur XML-RPC server for accounting        
        '''
        parameters = self.get_production_parameter(cr, uid, context=context)
        try:
            mx_parameter_server = parameters.production_host
            mx_parameter_port = parameters.production_port

            xmlrpc_server = "http://%s:%s" % (
                mx_parameter_server,
                mx_parameter_port,
            )
        except:
            raise osv.except_osv(
                _('Import CL error!'),
                _('XMLRPC for calling importation is not response'), )

        return xmlrpclib.ServerProxy(xmlrpc_server)

    _columns = {
        'production_export': fields.boolean('Production export', required=False, help="Enable export of CL and SL document via XML-RPC with exchange file"),
        'production_demo': fields.boolean('Production demo', required=False, help="Jump XMLRPC for demo test"),
        'production_mount_mandatory': fields.boolean('Mount mandatory', required=False, help="Test if folder for interchange files must be mounted"),
        'production_host': fields.char('Production XMLRPC host', size=64, required=False, readonly=False, help="Host name, IP address: 10.0.0.2 or hostname: server.example.com"),
        'production_port': fields.integer('MS SQL server port', required=False, readonly=False, help="XMLRPC port, example: 8000"),
        'production_cl': fields.char('Production interchange file CL', size=64, required=False, readonly=False, help="File name for CL exhange file"),
        'production_cl_upd': fields.char('Production interchange file SL', size=64, required=False, readonly=False, help="File name for SL exhange file"),
        'production_sl': fields.char('Production interchange file SL', size=64, required=False, readonly=False, help="File name for SL exhange file"),

        # Mount point:
        'production_path': fields.text('Production interchange path', required=False, readonly=False, help="Path of folder used for interchange, passed as a list: ('~','home','exchange')"),
        #'production_mount_unc':fields.char('Windows UNC name', size=64, required=False, readonly=False, help="Example: //server_ip/share_name"),
        #'production_mount_user':fields.char('Windows user for mount resource', size=64, required=False, readonly=False),
        #'production_mount_password':fields.char('Windows user for mount resource', size=64, required=False, readonly=False, password=True),
        #'production_mount_sudo_password':fields.char('Linux sudo password', size=64, required=False, readonly=False, password=True),
        #'production_mount_uid':fields.char('Linux user group for mount resource', size=64, required=False, readonly=False),
        #'production_mount_gid':fields.char('Linux user group for mount resource', size=64, required=False, readonly=False),
    }    
    _defaults = {
        'production_demo': lambda *x: False,
        'production_mount_mandatory': lambda *x: True,
        'production_port': lambda *a: 8000,
        'production_cl': lambda *a: "cl.txt",
        'production_sl': lambda *a: "sl.txt",
        'production_cl_upd': lambda *a: "cl_upd.txt",
        'production_export': lambda *a: False,
        
        #'production_mount_user': lambda *a: "administrator",
        #'production_mount_uid': lambda *a: "openerp",
        #'production_mount_gid': lambda *a: "openerp",
    }
res_company()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
