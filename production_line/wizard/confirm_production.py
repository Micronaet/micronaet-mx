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
from openerp.osv import osv, fields
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class confirm_mrp_production_wizard(osv.osv_memory):
    ''' Wizard that confirm production/lavoration
    '''
    _name = "mrp.production.confirm.wizard"

    # -------------------------------------------------------------------------
    #                             Utility function
    # -------------------------------------------------------------------------
    def get_parameter(self, cr, uid, context=None):
        ''' Get parameter browse obj for connection info
        '''
        try:
            parameter = self.pool.get('res.company').get_production_parameter(
                cr, uid, context=context)

            if not parameter:
                raise osv.except_osv(
                    _('Parameter error!'),
                    _('Problem reading parameters, test in Company window and setup '
                    'all parameters necessary!'))

            if not parameter.production_export:
                raise osv.except_osv(
                    _('Export non enabled!'),
                    _('The exportation of CL and SL is not enabled, check and fix in '
                    'Company window to setup parameters!'))

            if not all ((
                    parameter.production_host,
                    parameter.production_port,
                    parameter.production_path,
                    parameter.production_cl,
                    parameter.production_sl,
                    parameter.production_cl_upd,
                )):
                raise osv.except_osv(
                    _("Parameter error!"),
                    _("Problem reading parameters (someone is not present), "
                    "test in Company window and setup all parameters necessary!"))
        except:
            raise osv.except_osv(
                _("Parameter error!"),
                _("Problem reading parameters!"))
        return parameter        

    def get_interchange_files(self, cr, uid, parameter, context=None):
        ''' Return 3 interchange file name
        '''
        try:
            path_list = eval(parameter.production_path)
            path = os.path.expanduser(os.path.join(*path_list))

            if not parameter.production_demo and parameter.production_mount_mandatory and not os.path.ismount(path):
                # Test if the folder is mounted (here is a UNC mount)
                raise osv.except_osv(
                    _('Mount error!'),
                    _('Interchange path is not mount %s!') % (path, ))

            file_cl = os.path.join(path, parameter.production_cl)
            file_cl_upd = os.path.join(path, parameter.production_cl_upd)
            file_sl =  os.path.join(path, parameter.production_sl)
        except:
            raise osv.except_osv(
                _("Interchange file!"),
                _("Error create interchange file name!"))
        return file_cl, file_cl_upd, file_sl
        
    def get_xmlrpc_server(self, cr, uid, parameter, context=None):
        ''' Configure and retur XML-RPC server for accounting        
        '''
        try:
            mx_parameter_server = parameter.production_host
            mx_parameter_port = parameter.production_port

            xmlrpc_server = "http://%s:%s" % (
                mx_parameter_server,
                mx_parameter_port,
            )
        except:
            raise osv.except_osv(
                _('Import CL error!'),
                _('XMLRPC for calling importation is not response'), )
                
        return xmlrpclib.ServerProxy(xmlrpc_server)
        
    # ---------------
    # Onchange event:
    # ---------------
    def onchange_package_id(self, cr, uid, ids, package_id, product_id, total, context=None):
        ''' Get selected package_id and calculate total package
        '''
        res = {}
        res['value'] = {}

        if package_id and product_id and total:
            pack_pool = self.pool.get('product.packaging')
            pack_ids = pack_pool.search(cr, uid, [
                ('product_id','=',product_id),
                ('ul','=',package_id)], context=context)
            if pack_ids:
                pack_proxy=pack_pool.browse(cr, uid, pack_ids, context=context)[0]
                q_x_pack = pack_proxy.qty or 0.0
                res['value']['ul_qty'] = total // q_x_pack + (0 if total % q_x_pack == 0 else 1)
                return res
        res['value']['ul_qty'] = 0
        return res

    def onchange_pallet_id(self, cr, uid, ids, pallet_product_id, real_product_qty, pallet_max_weight, context=None):
        ''' Get total pallet with real qty and pallet selected
        '''
        res = {}
        res['value'] = {}
        res['value']['pallet_qty'] = 0.0
        res['value']['pallet_max_weight'] = 0.0

        try:
            if pallet_product_id and real_product_qty:
                if not pallet_max_weight:
                    pallet_max_weight = self.pool.get('product.product').browse(
                        cr, uid, pallet_product_id, context=context).pallet_max_weight or 0.0
                res['value']['pallet_qty'] = real_product_qty // pallet_max_weight + (0 if real_product_qty % pallet_max_weight == 0 else 1)
                res['value']['pallet_max_weight'] = pallet_max_weight
        except:
            pass # set qty to 0.0
        return res
    # --------------
    # Wizard button:
    # --------------
    def action_confirm_mrp_production_order(self, cr, uid, ids, context=None):
        ''' Write confirmed weight
        '''
        if context is None:
            context = {}

        wiz_proxy = self.browse(
            cr, uid, ids, context=context)[0]
        current_lavoration_id = context.get("active_id", 0)

        # ---------------------------------------------------------------------
        #                          Initial setup:
        # ---------------------------------------------------------------------
        # get parameters
        parameter = self.get_parameter(cr, uid, context=context)
        wf_service = netsvc.LocalService("workflow")
        error_prefix = "#ERR" # TODO configuration area?

        # Interchange file:
        file_cl, file_cl_upd, file_sl = self.get_interchange_files(
            cr, uid, parameter, context=context)
        
        # XMLRPC server:
        mx_server = self.get_xmlrpc_server(cr, uid, parameter, context=context)

        # ---------------------------------------------------------------------
        #                               Load pool
        # ---------------------------------------------------------------------
        lavoration_pool = self.pool.get("mrp.production.workcenter.line")
        product_pool = self.pool.get('product.product')
        load_pool = self.pool.get('mrp.production.workcenter.load')

        lavoration_browse = lavoration_pool.browse(
            cr, uid, current_lavoration_id, context=context)

        # Only if not to close have a partial or fully load:
        # 1. First close: all material are unloaded from stock accounting
        # 2. From second to last: all product are loaded with unload package
        # 3. Last: also correct product price
        if wiz_proxy.state == 'product':
            # -----------------------------------------------------------------
            #                      CL  (lavoration load)
            # -----------------------------------------------------------------
            # Verify thet if is the last load no lavoration are open:
            if not wiz_proxy.partial:
                for l in lavoration_browse.production_id.workcenter_lines:
                    if l.state not in ('done', 'cancel'): # not closed
                        raise osv.except_osv(
                            _('Last lavoration:'),
                            _('When is the last lavoration all lavoration must be in closed state!'))
            if lavoration_browse.production_id.accounting_state in ('cancel'):
                raise osv.except_osv(
                    _('Production error:'),
                    _('Could not add other extra load (production cancelled)!'))
            if wiz_proxy.package_id and not wiz_proxy.ul_qty:
                raise osv.except_osv(
                    _('Package error:'),
                    _('If package is present quantity is mandatory!'))
            if wiz_proxy.pallet_product_id and not wiz_proxy.pallet_qty:
                raise osv.except_osv(
                    _('Pallet error:'),
                    _('If pallet is present quantity is mandatory!'))

            # Create movement in list:
            product_qty = wiz_proxy.real_product_qty or 0.0
            wrong = wiz_proxy.wrong
            recycle = wiz_proxy.recycle
            recycle_product_id = wiz_proxy.recycle_product_id
            package_id = wiz_proxy.package_id.id if wiz_proxy.package_id else False
            price = 0.0   # TODO create a function for compute: sum ( q. x std. cost)
            load_id = load_pool.create(cr, uid, {
                'product_qty': product_qty, # only the wrote total
                'line_id': lavoration_browse.id,
                'partial': wiz_proxy.partial,
                'package_id': package_id,
                'ul_qty': wiz_proxy.ul_qty,
                'pallet_product_id': wiz_proxy.pallet_product_id.id if wiz_proxy.pallet_product_id else False,
                'pallet_qty': wiz_proxy.pallet_qty or 0.0,
                'recycle': recycle,
                'recycle_product_id': recycle_product_id.id if recycle_product_id else False,
                'wrong': wrong,
                'wrong_comment': wiz_proxy.wrong_comment,
            })
            sequence = load_pool.browse( # TODO crearla in funzione della produzione
                cr, uid, load_id, context=context).sequence # reload record for get sequence value

            # TODO manage recycle product!!!!! <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

            # [(1)Famiglia-(6)Prodotto-(1).Pezzatura-(1)Versione]-[(5)Partita-#(2)SequenzaCarico]-[(10)Imballo]
            product_code = "%-8s%-2s%-10s%-10s" % (
                wiz_proxy.product_id.default_code,                                            # Product code
                lavoration_browse.workcenter_id.code[:2],                                     # Workcenter
                "%06d#%01d" % (
                    int(lavoration_browse.production_id.name[3:]),
                    sequence,
                ),    # Job         <<<<<<< TODO use production (test, production is 5)
                wiz_proxy.package_id.code if package_id else "",                              # Package
            )
            load_pool.write(cr, uid, load_id, {'product_code': product_code}, context=context)

            ### Write load on accounting: # TODO potrebbe generare problemi se annullassero carichi o cose del genere!!!
            # Better: reload from dbmirror (but in real time)
            product_pool.write(cr, uid, lavoration_browse.production_id.product_id.id,    # Now update accounting_qty on db for speed up
                {'accounting_qty': (lavoration_browse.production_id.product_id.accounting_qty or 0.0) + (wiz_proxy.real_product_qty or 0.0),
            }, context=context)

            # Export CL for product with new generated code:
            try:
                f_cl = open(file_cl, "w")
            except:
                raise osv.except_osv(
                    _('Transit file!'),
                    _('Problem accessing file: %s (maybe open in accounting program)!') % file_cl)

            if wrong: # if wrong new code is generated ((recycle code = code with R in 8th position)
                f_cl.write("%-35s%10.2f%10.2f\r\n" % (
                    "%sR%s" % (product_code[:7],
                    product_code[8:]),
                    product_qty,
                    price))
            else:
                f_cl.write("%-35s%10.2f%10.2f\r\n" % (
                    product_code, product_qty, price))

            # TODO mode in product (end movement)
            convert_load_id = {} # list for convert CL code in load.id
            #for load in lavoration_browse.load_ids:

            # -----------------------------------------------------
            # Export SL form package/pallet used in loaded products
            # -----------------------------------------------------
            if wiz_proxy.package_id and wiz_proxy.ul_qty:
                f_cl.write(
                    "%-10s%-25s%10.2f%-10s\r\n" % ( # TODO 10 extra space
                        wiz_proxy.package_id.linked_product_id.default_code,
                        " " * 25, #lavoration_browse.name[4:],
                        - wiz_proxy.ul_qty,
                        lavoration_browse.accounting_sl_code, #" " * 10, # no value
                    ))
            else:
                pass # TODO raise error if no package? (no if wrong!)
            if wiz_proxy.pallet_product_id and wiz_proxy.pallet_qty:
                f_cl.write(
                    "%-10s%-25s%10.2f%-10s\r\n" % ( # TODO 10 extra space
                        wiz_proxy.pallet_product_id.default_code,
                        " " * 25, #lavoration_browse.name[4:],
                        - wiz_proxy.pallet_qty,
                        lavoration_browse.accounting_sl_code, #" " * 10, # no value
                    ))
            else:
                pass
                
            f_cl.close()

            # -----------------------------------------------------------------
            #                         Load CL for product
            # -----------------------------------------------------------------
            try:
                if parameter.production_demo: # Demo mode:
                    accounting_cl_code = 'DEMOCL000'
                else:
                    try:
                        accounting_cl_code = mx_server.sprix("CL")
                    except:    
                        raise osv.except_osv(
                            _('Import CL error!'),
                            _('XMLRPC error calling import CL procedure'), )

                    # test if there's an error during importation:
                    if accounting_cl_code.startswith(error_prefix): #  stat with: #ERR
                        raise osv.except_osv(
                            _('Import CL error!'),
                            _('Error from accounting:\n%s') % accounting_cl_code[len(error_prefix):],
                        )

                error = (
                    _('Update OpenERP with CL error!'),
                    _('Cannot write in OpenERP CL number for this load!'),
                )
                load_pool.write(cr, uid, load_id, {'accounting_cl_code': accounting_cl_code, }, context=context)

                # --------------------------------
                # Update lavoration with new info:
                # --------------------------------
                # TODO portare l'informazione sulla produzione qui non ha più senso con i carichi sballati
                total = 0.0 # net production total
                
                # Partial (calculated every load on all production)                
                for l in lavoration_browse.production_id.workcenter_lines:
                    for partial in l.load_ids:
                        total += partial.product_qty or 0.0

                # TODO togliere i commenti nei log e metterli magari nella lavorazione per sapere come sono stati calcolati
                _logger.info(_("Production real total: %s") % (total, ))
                ######################### data = {'real_product_qty': total}

                if not wiz_proxy.partial: # Last unload document (extra op. needed)
                    # TODO togliere il load_confirmed
                    ###################### data['load_confirmed'] = True # No other loads are permitted!
                    # ---------------------------------------------------------
                    #                     CL update price file
                    # ---------------------------------------------------------
                    try:        
                        f_cl_upd = open(file_cl_upd, "w")
                    except:    
                        raise osv.except_osv(
                            _('Transit file!'),
                            _('Problem accessing file: %s (maybe open in accounting program)!') % (
                                file_cl_upd))
                    unload_cost_total = 0.0

                    # ------------------
                    # Lavoration K cost:
                    # ------------------
                    try:
                        cost_line = lavoration_browse.workcenter_id.cost_product_id.standard_price or 0.0
                    except:
                        cost_line = 0.0

                    if not cost_line:    
                        raise osv.except_osv(
                            _('Calculate lavoration cost!'),
                            _('Error calculating lavoration cost, verifiy if the workcenter has product linked'), )

                    unload_cost_total = cost_line * total
                    _logger.info(_("Lavoration %s [%s]") % (
                        cost_line, unload_cost_total, ))

                    # ----------------------------------------------
                    # All unload cost of materials (all production):
                    # ----------------------------------------------
                    for lavoration in lavoration_browse.production_id.workcenter_lines:
                        for unload in lavoration.bom_material_ids:
                            try:
                                unload_cost_total += unload.product_id.standard_price * unload.quantity
                            except:
                                _logger.error(_("Error calculating unload lavoration"))    
                    _logger.info(_("With materials [%s]") % (unload_cost_total, ))

                    # ------------------------------
                    # All unload package and pallet:
                    # ------------------------------
                    for l in lavoration_browse.production_id.workcenter_lines:                    
                        for load in l.load_ids:
                            try:
                                # Package:
                                if load.package_id: # there's pallet
                                    unload_cost_total += load.package_id.linked_product_id.standard_price * load.ul_qty
                                    _logger.info(_("Package cost %s [%s]") % (
                                        load.package_id.linked_product_id.standard_price, 
                                        load.ul_qty,
                                    ))
                            except:
                                _logger.error(_("Error calculating package price"))    
                                
                            try:
                                # Pallet:
                                if load.pallet_product_id: # there's pallet
                                    unload_cost_total += load.pallet_product_id.standard_price * load.pallet_qty
                                    _logger.info(_("Pallet cost %s [%s]") % (
                                        load.pallet_product_id.standard_price,
                                        load.pallet_qty,
                                    ))
                            except:
                                _logger.error(_("Error calculating pallet price"))    
                                
                    unload_cost = unload_cost_total / total
                    _logger.info(_("With package  %s [unit.: %s]") % (
                        unload_cost_total, unload_cost, ))

                    # Update all production with value calculated: #TODO serve?
                    for l in lavoration_browse.production_id.workcenter_lines:                    
                        for load in l.load_ids:
                            load_pool.write(cr, uid, load.id, {
                                'accounting_cost': unload_cost * load.product_qty,
                            }, context=context)

                            # Export CL for update product price:
                            if not load.accounting_cl_code:
                                raise osv.except_osv(
                                    _('CL list!'),
                                    _('Error CL without number finded!'), )
                                
                            accounting_cl_code = load.accounting_cl_code.strip()
                            f_cl_upd.write(
                                "%-6s%10.5f\r\n" % (
                                    accounting_cl_code,
                                    unload_cost, ), # unit
                                )
                            convert_load_id[accounting_cl_code] = load.id
                            # TODO problema con il file di ritorno !!!!!!!!!!!!!!!

                    # Temporary update accounting_qty on db for speed up (till new synd for product state with correct value)
                    # TODO Verificare perchè dovrebbe essere già stato tolto alla creazione della CL!!
                    #product_pool.write(cr, uid, unload.product_id.id, {'accounting_qty':(unload.accounting_qty or 0.0) - (unload.quantity or 0.0),}, context=context)
                    # TODO Vedere per scarico imballaggi
                    f_cl_upd.close()

                    # ---------------------------------------------------------
                    #                   CL update for product cost
                    # ---------------------------------------------------------
                    error = (
                        _('Update CL error!'),
                        _('XMLRPC for calling update CL method'), )

                    if not parameter.production_demo: # Demo mode:
                        res_list = mx_server.sprix("CLW") # testare per verificare i prezzi   >>> list of tuple [(1000, True),(2000, False)] >> (cl_id, updated)
                        if not res_list:
                            raise osv.except_osv(
                                _('Update CL price error!'),
                                _('Error launchind update CL price command'),
                            )
                        error = (
                            _('Update loaded CL price error!'),
                            _('Error during confirm the load or price for product in accounting program!'),
                        )
                        for (key,res) in res_list:
                            load_id = convert_load_id[key]
                            if res: # if True update succesfully
                                load_pool.write(
                                    cr, uid, load_id,
                                    {'accounting_cost_confirmed': True},
                                    context=context)
                            else:
                                pass # TODO raise error?

                    # ---------------------------------------------------------
                    #            Real workflow operation (only last load)
                    # ---------------------------------------------------------
                    # TODO Non occorre più verificare togliee questa parte:
                    # Close production order:
                    #if lavoration_browse.production_id.accounting_state in ('draft', 'production'):
                    #    if lavoration_browse.production_id.accounting_state in ('production'):
                    #        all_closed = True
                    #        for lavoration in lavoration_browse.production_id.workcenter_lines:
                    #            if lavoration.state not in ('done','cancel'):
                    #                all_closed = False
                    #                break
                    #        if all_closed:
                    wf_service.trg_validate(
                        uid, 'mrp.production', 
                        lavoration_browse.production_id.id,
                        'trigger_accounting_close',
                        cr)

                # togliere: scriveva il totale carito e il load_confirmed
                #lavoration_pool.write(cr, uid, [lavoration_browse.id], data, context=context)
            except:
                raise osv.except_osv(_("Generic error"), "%s" % (sys.exc_info(), )) #error[0], "%s [%s]" % (error[1], sys.exc_info()) )

        else: # state == 'material' >> unload all material and package:
            # -----------------------------------------------------------------
            #                              SL Document
            # -----------------------------------------------------------------
            try: # SL file:
                f_sl = open(file_sl, "w")

                for unload in lavoration_browse.bom_material_ids:
                    # Export SL for material used for entire production:
                    f_sl.write("%-10s%-25s%10.2f\r\n" % (
                        unload.product_id.default_code,
                        lavoration_browse.name[4:],
                        unload.quantity))
                    try:
                        product_pool.write(cr, uid, [unload.product_id.id],    # Now update accounting_qty on db for speed up
                            {'accounting_qty': (unload.product_id.accounting_qty or 0.0) - (unload.quantity or 0.0), },
                        context=context)
                    except:
                        pass # no error raise if problems
                f_sl.close()
            except:
                raise osv.except_osv(
                    _('Transit file SL:'),
                    _('Problem accessing file: %s (maybe open in accounting program or error during export)!') % (file_sl),
                )

            # -----------------------------------------------------------------
            #                      XMLRPC call for import SL 
            # -----------------------------------------------------------------
            try: # an error here could mean that the document is created in accounting program #TODO manage this problem
                if parameter.production_demo:
                    accounting_sl_code = "DEMOSL000"
                else:
                    # ---------------------------------------------------------
                    #               SL for material and package
                    # ---------------------------------------------------------
                    try:
                        accounting_sl_code = mx_server.sprix("SL")
                    except:    
                        raise osv.except_osv(
                        _('Import SL error!'),
                        _('XMLRPC error calling import SL procedure'), )

                    # Test if there's an error during importation:
                    if accounting_sl_code.startswith(error_prefix): #  stat with: #ERR
                        raise osv.except_osv(
                            _('Import SL error!'),
                            _('Error from accounting:\n%s') % (
                                accounting_sl_code[4:], ))

                error = (
                    _('Update SL error!'),
                    _('Error updating yet created SL link in OpenERP'),
                )
                lavoration_pool.write(
                    cr, uid, [current_lavoration_id],
                    {
                        'accounting_sl_code': accounting_sl_code,
                        'unload_confirmed': True, # TODO non dovrebbe più servire # Next "confirm" is for prod.
                    },
                    context=context)

                try:  # If not error till now close WF for this lavoration:
                    wf_service.trg_validate(
                        uid, 'mrp.production.workcenter.line',
                        current_lavoration_id, 'button_done', cr)
                except:    
                    raise osv.except_osv(
                    _('Workflow error:'),
                    _('Error closing lavoration!'), )
            except:
                raise osv.except_osv(*error)                
        return {'type':'ir.actions.act_window_close'}

    # -----------------
    # default function:
    # -----------------
    def default_quantity(self, cr, uid, context=None):
        ''' Get default value
        '''
        wc_pool = self.pool.get('mrp.production.workcenter.line')
        wc_browse = wc_pool.browse(cr, uid, context.get('active_id', 0), context=context)
        
        total = 0.0
        try:
            for l in wc_browse.production_id.workcenter_lines:
                total += l.product_qty - sum([load.product_qty for load in l.load_ids])
        except:
            total = 0.0  
        return total


    #def default_mode(self, cr, uid, context=None):
    #    ''' Setup open mode of wizard depend of status check
    #    '''
    #    wc_pool = self.pool.get('mrp.production.workcenter.line')
    #    active_id = context.get("active_id", 0)
    #    if active_id:
    #        wc_browse = wc_pool.browse(
    #            cr, uid, context.get("active_id", 0), context=context)
    #        if wc_browse.unload_confirmed:
    #            return 'product'
    #        else:
    #            return 'material'
    #    return 'matarial' # default

    #def default_to_close(self, cr, uid, context=None):
    #    ''' Get default value, if load_confirmed so to_close is True
    #    '''
    #    wc_pool = self.pool.get('mrp.production.workcenter.line')
    #    if context.get("active_id", 0):
    #        wc_browse = wc_pool.browse(
    #            cr, uid, context.get("active_id", 0), context=context)
    #        return wc_browse.load_confirmed
    #    return False # not launched during wizard

    def default_list_unload(self, cr, uid, context=None):
        ''' Get default value, if load_confirmed so to_close is True
        '''
        wc_pool = self.pool.get('mrp.production.workcenter.line')
        res = ""
        active_id = context.get("active_id", 0)
        if active_id:
            wc_browse = wc_pool.browse(cr, uid, active_id, context=context)
            res = "Material:\n"
            for unload in wc_browse.bom_material_ids:
                res += "[%s %s] - %s\n" % (
                    unload.quantity,
                    unload.uom_id.name,
                    unload.product_id.name,
                )

            # TODO Manage in production load
            #res += "\nPackage:\n"
            #for load in wc_browse.load_ids:
            #    if load.package_id:
            #        res += "Load %s. [%s] - %s%s\n" % (
            #            load.sequence,
            #            load.ul_qty,
            #            load.package_id.name,
            #            "\t\t<<<< No q.ty (not exported in SL)! <<<<<" if (
            #                load.package_id and not load.ul_qty) else "")
            #    else:
            #        res += "Load %s. Wrong product is without package (not exported in SL)\n" % (
            #            load.sequence)
        return res

    def default_product(self, cr, uid, context=None):
        ''' Get default value for product (get from product order)
        '''
        wc_pool = self.pool.get('mrp.production.workcenter.line')

        if context.get("active_id", 0):
            wc_browse = wc_pool.browse(
                cr, uid, context.get("active_id", 0), context=context)
            return wc_browse.product.id if wc_browse.product else False
        return False

    _columns = {
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'real_product_qty': fields.float('Confirm production', digits=(16, 2), required=True),
        'partial': fields.boolean('Partial', required=False, help="If the product qty indicated is a partial load (not close lavoration)"),
        'confirm_material': fields.boolean('Confirm material', required=False, help="This confirm update of material on account program and close definitively the lavoration!"),

        'package_id': fields.many2one('product.ul', 'Package', required=False),
        'ul_qty': fields.integer('Package q.', help="Package quantity to unload from accounting"),
        'linked_product_id': fields.related('package_id', 'linked_product_id', type='many2one', relation='product_product', string='Linked product'),

        'pallet_product_id': fields.many2one('product.product', 'Pallet', required=False),
        'pallet_max_weight': fields.float('Max weight', digits=(16, 2), help="Max weight per pallet"),
        'pallet_qty': fields.integer('Pallet q.', help="Pallet total number"),

        #'to_close': fields.boolean('To close', required=False, help="If the load is set ad not partial"), # TODO remove
        'list_unload': fields.text('List unload'),

        'recycle': fields.boolean('Recycle', required=False, help="Recycle product"),
        'recycle_product_id': fields.many2one('product.product', 'Product', required=False),

        'wrong': fields.boolean('Wrong', required=False, help="Wrong product, coded with a standard code"),
        'wrong_comment': fields.text('Wrong comment'),
        'state': fields.selection( # there's not a WF, only a check
            [
                ('material', 'Unload materials'),
                ('product', 'Load product (unload package')
            ],
            'Mode',
            readonly=True),
        }

    _defaults = {
        'product_id': lambda s, cr, uid, c: s.default_product(cr, uid, context=c),
        'real_product_qty':  lambda s, cr, uid, c: s.default_quantity(cr, uid, context=c),
        'partial': lambda *a: True,
        'wrong': lambda *a: False,
        'confirm_material': lambda *a: False,
        #'to_close': lambda s, cr, uid, c: s.default_to_close(cr, uid, context=c),
        'list_unload': lambda s, cr, uid, ctx: s.default_list_unload(cr, uid, context=ctx),
        #'state': lambda s, cr, uid, ctx: s.default_mode(cr, uid, context=ctx),
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
