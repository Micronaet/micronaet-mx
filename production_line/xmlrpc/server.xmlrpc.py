#!/usr/bin/python
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
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import ConfigParser


# -----------------------------------------------------------------------------
#                                Parameters
# -----------------------------------------------------------------------------

config = ConfigParser.ConfigParser()
config.read(['./openerp.cfg'])

# XMLRPC server:
xmlrpc_host = config.get('XMLRPC', 'host') 
xmlrpc_port = eval(config.get('XMLRPC', 'port'))

path = config.get('mexal', 'path') #"c:\mexal_cli\prog"
company_code = config.get('mexal', 'company')

# Access:
mx_user = config.get('mexal', 'user')
mx_login = config.get('mexal', 'login')

# Sprix:
sprix_cl = eval(config.get('mexal', 'sprix_cl')) #125
sprix_cl_upd = eval(config.get('mexal', 'sprix_cl_upd')) # 126
sprix_sl = eval(config.get('mexal', 'sprix_sl')) # 127
sprix_bom = eval(config.get('mexal', 'sprix_bom')) # 608
sprix_move = eval(config.get('mexal', 'sprix_move')) # 128 # TODO verificare!

# Parameters calculated:
# Transit files:
file_cl = r"%s\production\%s" % (path, "esito_cl.txt")
file_cl_upd = r"%s\production\%s" % (path, "esito_cl_upd.txt")
file_sl = r"%s\production\%s" % (path, "esito_sl.txt")

# Files for stock movement:
file_move = r"%s\production\%s" % (path, "move.txt")
file_move_res = r"%s\production\%s" % (path, "esito_move.txt")
# Note: result file are the same with "esito_" before file name

sprix_command = r"%s\mxdesk.exe -command=mxrs.exe -login=openerp -t0 -x2 win32g -p#%s -a%s -k%s:%s" % (
    path, "%s", company_code, mx_user, mx_login)

# -----------------------------------------------------------------------------
#                         Restrict to a particular path
# -----------------------------------------------------------------------------
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# -----------------------------------------------------------------------------
#                                Create server
# -----------------------------------------------------------------------------
server = SimpleXMLRPCServer(
    (xmlrpc_host, xmlrpc_port), requestHandler=RequestHandler)
server.register_introspection_functions()

# -----------------------------------------------------------------------------
#                                 Functions
# -----------------------------------------------------------------------------
def sprix(operation, parameters=None):
    ''' Call mxrs program passing sprix number
    '''
    if parameters is None:
        parameters = {}
    # --------
    # Utility:
    # --------
    def get_res(transit_file, is_list=False):
        """ Read result files, composed ad transit_file with "esito_" before
            return value of the only one line that is present
        """
        try:
            res_file = open(transit_file, "r")
            
            if is_list:
                res = []
                for item in res_file:
                    code = item[:6].strip()
                    operation = "OK" == item[6:8].upper()
                    res.append((code, operation))
            else:        
                res = res_file.read().strip()

            res_file.close()
            os.remove(transit_file)    
            return res                
        except:
            return False # for all errors    

        
    # -------------------------------------------------------------------------
    #                        Cases (operations):
    # -------------------------------------------------------------------------    
    if operation.upper() == "CL": 
        # Call sprix for create CL:
        try:
            os.system(sprix_command % sprix_cl)            
        except:
            return "#Error launching importation CL command" # on error    
        
        # get result of operation:
        return get_res(file_cl) 
        
    elif operation.upper() == "CLW": 
        # Call sprix for update price in CL: 
        try:
            os.system (sprix_command % sprix_cl_upd)
        except:
            return False # on error    
        
        # get result of operation:
        return get_res(file_cl_upd, is_list=True)
        
    elif operation.upper() == "SL": 
        # Call sprix for create SL:
        try:
            os.system (sprix_command % sprix_sl)
        except:
            return "#Error launching importation SL command" # on error    
        
        # get result of operation:
        return get_res(file_sl) 

    elif operation.upper() == "MOVE": 
        # Call sprix for move data from lot to another:
        try:
            # Create files from line passed
            line = paramaters.get('line', False)
            if not line:
                return "#Error movement line not present!"
            try:    
                f = open(file_move, "w")
                f.write(line)
                f.close()
            except:
                return "#Error creating transit file!"            
            os.system (sprix_command % sprix_move)
        except:
            return "#Error launching importation SL command" # on error    
        
        # get result of operation:
        return "" #get_res(file_move_res)  # TODO leggere e tornare eventuale errore!

    elif operation.upper() == "BOM": 
        # Call sprix for create BOM:
        try:
            os.system (sprix_command % sprix_bom)
        except:
            return "#Error launching export BOM" 
        
        # get result of operation:
        return get_res(file_sl) 

    return False # error

# -----------------------------------------------------------------------------
#                  Register Function in XML-RPC server:
# -----------------------------------------------------------------------------
server.register_function(sprix, 'sprix')

# -----------------------------------------------------------------------------
#                       Run the server's main loop:
# -----------------------------------------------------------------------------
server.serve_forever()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

