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
from openerp.osv import osv, fields
from datetime import datetime, timedelta
from openerp import tools
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, DATETIME_FORMATS_MAP, float_compare)
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
from utility import *


_logger = logging.getLogger(__name__)

class mail_thread(osv.osv):
    ''' Add extra function for changing state in mail.thread
    '''
    _inherit = 'mail.thread'
    _name = 'mail.thread'

    # --------
    # Utility:
    # --------
    def write_thread_message(self, cr, uid, ids, subject='', body='', context=None):
        ''' Write generic message 
            # TODO unificare con quello dello stato
        '''
        # Default part of message:
        message = { 
            'subject': subject,
            'body': body,
            'type': 'comment', #'notification', 'email',
            'subtype': False,  #parent_id, #attachments,
            'content_subtype': 'html',
            'partner_ids': [],            
            'email_from': 'openerp@micronaet.it', #wizard.email_from,
            'context': context,
            }
        msg_id = self.message_post(cr, uid, ids, **message)
        return 
        
    def write_object_change_state(self, cr, uid, ids, state='state', context=None):
        ''' Write info in thread list (used in WF actions)
        '''
        current_proxy = self.browse(cr, uid, ids, context=context)[0]

        # Default part of message:
        message = { 
            'subject': _("Changing state:"),
            'body': _("State variation in <b>%s</b>") % current_proxy.__getattr__(state),
            'type': 'comment', #'notification', 'email',
            'subtype': False,  #parent_id, #attachments,
            'content_subtype': 'html',
            'partner_ids': [],            
            'email_from': 'openerp@micronaet.it', #wizard.email_from,
            'context': context,
            }
        #message['partner_ids'].append(task_proxy.assigned_user_id.partner_id.id)
        self.message_subscribe_users(
            cr, uid, ids, user_ids=[uid], context=context)
                        
        msg_id = self.message_post(cr, uid, ids, **message)
        #if notification: 
        #    _logger.info(">> Send mail notification! [%s]" % message['partner_ids'])
        #    self.pool.get(
        #        'mail.notification')._notify(cr, uid, msg_id, 
        #        message['partner_ids'], 
        #        context=context
        #        )       
        return    
        
class res_company_send_mail(osv.osv):
    ''' Add utility function for send mail
    '''
    _name = "res.company"
    _inherit = "res.company"

    # TODO Riscrivere con la gestione dei thread
    def send_mail(self, cr, uid, subject, body, 
            to_addr='nicola.riolini@gmail.com', 
            from_addr='OpenERP <openerp@micronaet.it>', context=None):
        ''' Procedure for send control mail during importation
            Use default parameter for sending
            @return: False if mail is not sent
        '''
        from smtplib import SMTP

        server_ids = self.pool.get('ir.mail_server').search(
            cr, uid, [], context=context)
        if not server_ids:
            return False

        server_smtp = self.pool.get('ir.mail_server').browse(
            cr, uid, server_ids[0], context=context)
        smtp = SMTP()
        smtp.set_debuglevel(0)
        smtp.connect(server_smtp.smtp_host, server_smtp.smtp_port)
        smtp.login(server_smtp.smtp_user, server_smtp.smtp_pass)

        date = datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        smtp.sendmail(
            from_addr, to_addr,
            "From: %s\nTo: %s\nSubject: %s\nDate: %s\n\n%s" % (
                from_addr,
                to_addr,
                subject,
                date,
                body,
            ), )
        smtp.quit()
        return True

class sale_order_add_extra(osv.osv):
    ''' Create import scheduled action
        Add extra field for manage termporary order in account program (for
        production and delivery decision)
    '''
    _name = "sale.order"
    _inherit = "sale.order"

    # -------------------------------------------------------------------------
    #                              Utility function
    # -------------------------------------------------------------------------
    def get_uom(self, cr, uid, name, context=None):
        uom_id = self.pool.get('product.uom').search(cr, uid, [
            ('name', '=', name), ])
        if uom_id:
            return uom_id[0] # take the first
        else:
            return False

    # TODO spostare in un posto migliore (o integrarlo nella gestione importaz.)
    def send_mail(self, cr, uid, subject, body, context=None):
        ''' Procedure for send control mail during importation
            @return: False if mail is not sent
        '''
        from smtplib import SMTP

        server_ids = self.pool.get('ir.mail_server').search(cr, uid, [
            ], context=context)
        if not server_ids:
            return False

        server_smtp = self.pool.get('ir.mail_server').browse(
            cr, uid, server_ids[0], context=context)
        smtp = SMTP()
        smtp.set_debuglevel(0) # debuglevel = 0
        smtp.connect(server_smtp.smtp_host, server_smtp.smtp_port)
        smtp.login(server_smtp.smtp_user, server_smtp.smtp_pass)

        from_addr = "OpenERP <openerp@micronaet.it>"
        to_addr = "nicola.riolini@gmail.com"
        date = datetime.now().strftime("%d/%m/%Y %H:%M")

        smtp.sendmail(from_addr, to_addr,
            "From: %s\nTo: %s\nSubject: %s\nDate: %s\n\n%s" % (
                from_addr, to_addr, subject, date, body),)
        smtp.quit()
        return True

    # -------------------------------------------------------------------------
    #                                 Button function
    # -------------------------------------------------------------------------
    def confirm_delivery(self, cr, uid, ids, context=None):
        ''' Change state for became mandatory the delivery date and block
            production orders
        '''
        order_proxy = self.browse(cr, uid, ids, context=context)[0]
        data = {'accounting_state': 'planned'}

        if not order_proxy.date_booked:
            data['date_booked'] = order_proxy.date_deadline or datetime.now(
                ).strftime(DEFAULT_SERVER_DATE_FORMAT)
        self.write(cr, uid, ids, data, context=context)
        return True

    # -------------------------------------------------------------------------
    #                                 Scheduled action
    # -------------------------------------------------------------------------
    def schedule_etl_sale_order(self, cr, uid, context=None):
        ''' Import OC and create sale.order
        '''
        empty_date = self.pool.get('micronaet.accounting').get_empty_date()
        log_info = ""

        is_to_produce_q = {}     # Update boolean if store value < sum(oc line q.)
        is_to_produce_line = {}  # ID for update boolean if store value < sum(oc line q.)

        # ---------------------------------------------------------------------
        #                                 Utility
        # ---------------------------------------------------------------------
        def get_oc_key(record):
            ''' Compose and return key for OC
            '''
            return (
                record['CSG_DOC'].strip(),
                record['NGB_SR_DOC'],
                record['NGL_DOC'],
            )

        # Open CSV passed file (see arguments) mode: read / binary, delimiation char
        _logger.info("Start import OC header")

        # ---------------------------------------------------------------------
        #                               IMPORT HEADER
        # ---------------------------------------------------------------------
        # TODO rimuovere questo problema alcuni ordini hanno state empty!
        cr.execute("update sale_order set state='draft' where state is null;")
        all_order_ids = self.search(cr, uid, [
            ('accounting_order', '=', True)]) # for delete extra elements (on update order id is deleted from here)
        all_order_updated_ids = [] # list of all modified orders header (for load lines to test deletion)

        cursor_oc = self.pool.get('micronaet.accounting').get_oc_header(cr, uid)
        if not cursor_oc:
            return log_error(
                self, cr, uid, "schedule_etl_sale_order",
                "Cannot connect to MSSQL OC_TESTATE"
            )

        oc_header = {} # save OpenERP ID  (ref, type, number)

        for oc in cursor_oc:
            try: # master error
                name = "%s/%s" % (
                    oc['NGL_DOC'],
                    oc['DTT_DOC'].strftime("%Y"),
                )
                oc_id = self.search(cr, uid, [
                    ('name', '=', name)], context=context)
                if oc_id: # update      # TODO test for deadline update
                    oc_id = oc_id[0]
                    if oc_id not in all_order_updated_ids:
                        all_order_updated_ids.append(oc_id)

                    oc_proxy = self.browse(cr, uid, oc_id, context=context)

                    # Possible error during importation:
                    #   1. partner not the same,
                    #   2. deadline changed (see in the line for value),
                    #   3. record deleted (after)
                    header = {}
                    if header: # not working for now, decide if is necessary
                        update = self.write(
                            cr, uid, oc_id, header, context=context)

                    try: # Remove from delete list of orders
                        all_order_ids.remove(oc_id) # Note: the lines are removed when remove the header
                    except:
                        pass # no error
                    # NOTE se lascio l'ordine ma semplicemente metto removed lo stato ed anche lo stato delle line rimane l'informazione nelle bolle di produzione

                else: # new:
                    partner_proxy = browse_partner_ref(
                        self, cr, uid, oc['CKY_CNT_CLFR'], context=context)
                    if not partner_proxy or not partner_proxy.id: # TODO better!
                        _logger.error(
                            "No partner found (created minimal): %s" % (
                                oc['CKY_CNT_CLFR']))
                        try:
                            partner_id = self.pool.get(
                                'res.partner').create(cr, uid, {
                                    'name': "Partner %s" % (oc['CKY_CNT_CLFR']),
                                    'active': True,
                                    'property_account_position': 1, # TODO parametrizzare
                                    'is_company': True,
                                    'employee': False,
                                    'parent_id': False,
                                    'mexal_c': oc['CKY_CNT_CLFR'], #customer: True,# OC so customer!
                                }, context=context)
                        except:
                             _logger.error(
                                 "Error creating minimal partner: %s [%s]" % (
                                     oc['CKY_CNT_CLFR'],
                                     sys.exc_info()))
                             continue # jump this OC
                    else:
                        partner_id = partner_proxy.id #if partner_proxy else False

                    oc_id = self.create(cr, uid, {
                        'name': name,                    # max 64
                        'accounting_order': True,        # comes from Accounting program
                        'origin': False,                 # Source Document
                        'picking_policy': 'direct',      # [["direct","Deliver each product when available"],["one","Deliver all products at once"]]
                        'order_policy': 'manual',        # [["manual","On Demand"],["picking","On Delivery Order"],["prepaid","Before Delivery"]]
                        'date_order': oc['DTT_DOC'].strftime("%Y-%m-%d"),
                        'partner_id': partner_id,
                        'user_id': uid,
                        'note': oc['CDS_NOTE'].strip(),  # Terms and conditions
                        #'state': 'draft',                # draft sent cancel waiting_date progress manual shipping_except invoice_except done
                        'invoice_quantity': 'order',     #  order procurement
                        'pricelist_id': partner_proxy.property_product_pricelist.id if partner_proxy else 1,  # product.pricelist   # TODO put default!!!
                        'partner_invoice_id': partner_id,
                        'partner_shipping_id': partner_id,
                        # accounting_state default = new             #order_line
                        # payment_term account.payment.term  'currency_id' # function   incoterm  # stock.incoterms # project_id # account.analytic.account
                        # partner_shipping_id #shipped #date_confirm #section_id # crm.case.section create_date: False, #invoice_ids #invoice_exists shop_id #client_order_ref   Customer Reference
                        # amount_tax #fiscal_position account.fiscal.position company_id #picking_ids #invoiced #portal_payment_options picked_rate #amount_untaxed #amount_total #invoiced_rate #message_unread
                    }, context=context)

                oc_key = get_oc_key(oc)
                if (oc_key) not in oc_header:
                    oc_header[oc_key] = [oc_id, False] # (ID, Deadline) # NOTE no deadline in header but take the first line for get it
            except:
                _logger.error("Problem with record: %s > %s"%(oc, sys.exc_info()))

        # Delete header (and line linked):
        for delete_id in all_order_ids: # TODO Notify that OC is deleted from account (delivery or deleted???):
            # Rule: order before - order update = order to delete
            try:
                self.unlink(cr, uid, [delete_id], context=context)
            except:
                _logger.error("Error delete order id: %s" % (delete_id,))
    
            #self.write(cr, uid, all_order_ids, {'accounting_order': False,}, context=context) # Not visible in production (only in lavorations)

        # ---------------------------------------------------------------------
        #                               IMPORT LINE
        # ---------------------------------------------------------------------
        _logger.info("Start import OC lines")
        line_pool = self.pool.get('sale.order.line')
        all_order_line_ids = line_pool.search(cr, uid, [
            ('order_id', 'in', all_order_updated_ids)], context=context)

        # Set all line as 'not confirmed':
        res = line_pool.write(cr, uid, all_order_line_ids, {
            'accounting_state': 'not'}, context=context)

        # Load all OC line in openerp in DB_line dict
        DB_line = {}
        for ol in line_pool.browse(cr, uid, all_order_line_ids, context=context):
            if ol.order_id.id not in DB_line:
                DB_line[ol.order_id.id] = []

            # ---------------
            # DB Line record:
            # ---------------
            DB_line[ol.order_id.id].append([
                ol.id,                   # ID
                False,                   # finded
                ol.product_id.id,        # product_id
                ol.date_deadline,        # deadline
                ol.product_uom_qty],     # q.
            )

        cursor_oc_line = self.pool.get('micronaet.accounting').get_oc_line(
            cr, uid)
        if not cursor_oc_line:
            return log_error(self, cr, uid,
                "schedule_etl_sale_order", "Cannot connect to MSSQL OC_RIGHE")
        for oc_line in cursor_oc_line:
            try: # master error
                oc_key = get_oc_key(oc_line)
                if oc_key not in oc_header:
                    _logger.error(
                        "Header order not found: OC-%s" % (oc_key[2])) # TODO manage warning!
                    continue

                # Get product browse from code:
                product_browse = browse_product_ref(
                    self, cr, uid, oc_line['CKY_ART'].strip(), context=context)
                if not product_browse:
                    _logger.info(
                        "No product found (OC line jumped): %s" % (
                            oc_line['CKY_ART'], ))
                    continue

                order_id = oc_header[oc_key][0]
                date_deadline = oc_line['DTT_SCAD'].strftime(
                    "%Y-%m-%d") if oc_line['DTT_SCAD'] and oc_line['DTT_SCAD'] != empty_date else False
                sequence = oc_line['NPR_RIGA'] # NOTE this is ID of line in OC (not really sequence order)

                uom_id = product_browse.uom_id.id if product_browse else False # uoms.get(uom, product_browse.uom_id.id if product_browse else False) # take default unit
                conversion = (
                    oc_line['NCF_CONV'] if oc_line['NCF_CONV'] else 1.0)
                quantity = (
                    oc_line['NQT_RIGA_O_PLOR'] or 0.0) * 1.0 / conversion

                # Save deadline in OC header (first time):
                if not oc_header[oc_key][1]:
                    if date_deadline: # take the first deadline for save in header delivery (TODO manage rewrite)
                        oc_header[oc_key][1] = True
                        mod = self.write(cr, uid, order_id, {
                            'date_deadline': date_deadline}, context=context)

                # common part of record (update/create):
                data = {
                    'name': oc_line['CDS_VARIAZ_ART'],  #product_browse.name if product_browse else "Art. # %s" % (oc_line['NPR_SORT_RIGA']),
                    'product_id': product_browse.id,
                    'product_uom_qty': quantity,
                    'product_uom': uom_id,
                    'price_unit': (oc_line['NPZ_UNIT'] or 0.0) * conversion,
                    'tax_id': [(6, 0, [product_browse.taxes_id[0].id, ])] if product_browse and product_browse.taxes_id else False, # CSG_IVA
                    'production_line': product_browse.supply_method == 'produce', # IMPORTANTE CORREGGERE METTENDOLO NELLA IMPORTAZIONE PRODOTTI production_line,
                    'to_produce': True,
                    'date_deadline': date_deadline,
                    'order_id': order_id,
                    'sequence': sequence, # id of row (not order field)
                    #'accounting_state': 'modified',
                }  # production_line

                # Syncronization part:
                mod = False
                if order_id in DB_line:
                    for element in DB_line[order_id]: # list of all the order line in OpenERP   [ID, finded, product_id, deadline, q.]
                        if element[1] == False and element[2] == product_browse.id and date_deadline == element[3]: # product and deadline
                            if abs(element[4] - quantity) < 1.0: # Q. different (with error)
                                data["accounting_state"] = "new"
                                element[1] = True # set this line as assigned! # TODO test!!
                            else:
                                data["accounting_state"] = "modified"

                            # Modify record:
                            oc_line_id = element[0]
                            mod = line_pool.write(
                                cr, uid, oc_line_id, data, context=context)
                            break # exit this for (no other lines as analyzed)

                if not mod: # Create record, not found: (product_id-date_deadline)
                    oc_line_id = line_pool.create(cr, uid, data, context=context)

                # Save data for accounting evaluations:
                if product_browse.id in is_to_produce_q:
                    is_to_produce_q[product_browse.id] += quantity or 0.0
                    is_to_produce_line[product_browse.id].append(oc_line_id)
                else:    # new element
                    is_to_produce_q[product_browse.id] = (quantity or 0.0) + product_browse.minimum_qty # Min q. + sum(all order Q)
                    is_to_produce_line[product_browse.id] = [oc_line_id]
            except:
                _logger.error("Problem with oc line record: %s\n%s" % (
                    oc_line,
                    sys.exc_info()
                ))

        # NOTE: only deleted lines with order still present!!!!:
        # ---------------------------------------------------------------------
        #                       Delete lines in production (logging)
        # ---------------------------------------------------------------------
        to_delete_ids = line_pool.search(cr, uid, [
            ('accounting_state', '=', 'not'),
            ('mrp_production_id', '!=', False)
        ]) # to delete (in production) # TODO log!
        if to_delete_ids:
            delete_oc_in_production_error = ""
            for item in line_pool.browse(cr, uid, to_delete_ids, context=context):
                delete_oc_in_production_error += "Order: %s (%s) [%s q.: %s] >> %s" % (
                    item.order_id.name,
                    item.date_deadline,
                    item.product_id.name,
                    item.product_uom_qty,
                    item.mrp_production_id.name
                )

            if delete_oc_in_production_error and self.send_mail(cr, uid, "Import sale order: Warning deletion of OC line in production", delete_oc_in_production_error, context=context):
                _logger.warning("Send mail for error / warning (OC line in production deleted)!")
            else:
                _logger.error("Server SMTP not setted up, no mail will be sent!")

            for del_id in to_delete_ids:
                try:
                    line_pool.unlink(cr, uid, [del_id], context=context) # delete directly
                except:   
                    _logger.warning(_("Unable to delete sale order %s!") % (del_id))

            # line_pool.write(cr, uid, to_delete_ids, {'accounting_state': 'deleted'},context=context) # set to deleted state
            _logger.info(
                "Deleted %s OC lines non present in Accounting (in production)!" % (
                    len(to_delete_ids),))

        # TODO IMPORTANTE: quanto verranno eliminati ordini se ci sono righe in produzione devono essere caricate come "use accounting store"
        # ---------------------------------------------------------------------
        #                  Delete lines not in production (logging)
        # ---------------------------------------------------------------------
        to_delete_ids = line_pool.search(cr, uid, [
            ('accounting_state', '=', 'not'),
            ('mrp_production_id', '=', False),
        ])
        # TODO solve the problem if order are confirmed or cancel...
        for item_id in to_delete_ids: # loop for manage error during deletion
            try:
                # TODO note: always error:
                line_pool.unlink(cr, uid, [item_id], context=context)
                _logger.info(
                    "Deleted %s OC lines non present in Accounting (in production)!" % (
                        item_id))
            except:
                _logger.warning(
                    "Problem delete a OC lines %s [%s]!" % (
                        item_id, sys.exc_info()))

        # ---------------------------------------------------------------------
        #                         Importation Analysis and log
        # ---------------------------------------------------------------------
        produce_product = []
        for product in self.pool.get('product.product').browse(cr, uid, is_to_produce_q.keys()):
            if product.accounting_qty > is_to_produce_q[product.id]:
                produce_product.extend(is_to_produce_line[product.id])
        line_pool.write(cr, uid, produce_product, {
            'to_produce': False})

        over_store_error = ""
        cr.execute("""
            SELECT 
                product_id, product_product.accounting_qty, 
                product_product.default_code, sum(product_uom_qty) total
            FROM sale_order_line
            LEFT JOIN product_product
            ON (sale_order_line.product_id = product_product.id)
            GROUP BY product_id, use_accounting_qty, product_product.default_code, product_product.accounting_qty
            HAVING use_accounting_qty = True and sum(product_uom_qty)>product_product.accounting_qty;""")

        for product_id, accounting_qty, default_code, total in cr.fetchall():
            over_store_error += "Product %s covered for %s but in accounting there's %s\n" % (
                default_code, total, accounting_qty)

        # Send mail for log error:
        if over_store_error:
            if self.send_mail(cr, uid, "Import sale order: Warning variation in store cover", over_store_error, context=context):
                _logger.warning("Send mail for error / warning (OC not covered with store)!")
            else:
                _logger.error("Server SMTP not setted up, no mail will be sent!")

        # TODO testare bene gli ordini di produzione che potrebbero avere delle mancanze!
        _logger.info("End importation OC header and line!")
        return

    _columns = {
        # TODO remove: (need to keep the data)!!!!
        #'date_deadline': fields.date('Deadline'),
        #'date_previous_deadline': fields.date('Previous deadline', help="If during sync deadline is modified this field contain old value before update"),
        #'mandatory_delivery': fields.boolean('Delivery mandatory', help='If true moving of order is not possible'),
        #'date_delivery': fields.date('Delivery', help="Contain delivery date, when present production plan work with this instead of deadline value, if forced production cannot be moved"),
        # TODO Moved in mx_sale ^^^^^^^

        'accounting_order': fields.boolean('Accounting order', help='It true the order is generated from accounting program, so it is temporarly present in OpenERP only for production and delivery operations'),
        'accounting_state': fields.selection([
            ('not', 'Not Confirmed'), # Not confirmed (first step during importation)
            ('new', 'New'),           # Confirmed
            ('modified', 'Modified'), # Quantity only (for production or linked to store)
            ('planned', 'Planned for delivery'),
            ('deleted', 'Deleted'),   # Not used (order vanished when delete order)
            ('close', 'Close'),       # Not used (order vanished when delete order)
        ],'Accounting state', select=True, readonly=True), }

    _defaults = {
        'accounting_order': lambda *x: False,
        'accounting_state': lambda *x: 'new',
        }

class sale_order_line_extra(osv.osv):
    ''' Create extra fields in sale.order.line obj
    '''
    _inherit = "sale.order.line"
    
    # -------------------------------------------------------------------------
    #                          Button events
    # -------------------------------------------------------------------------
    def button_duelist_exposition(self, cr, uid, ids, context=None):
        ''' List of exposition for this customer
        '''
        return True
        
    def free_line(self, cr, uid, ids, context=None):
        ''' Free the line from production order 
        '''
        return self.write(cr, uid, ids, {'mrp_production_id': False, }, context=context)
        
    def close_with_accounting_store(self, cr, uid, ids, context=None):
        ''' This button test if there's accounting quantity enought to close
            and link this line to the value
            If ok set order as linked removing the line from production
        '''
        # test yet checked lines
        sol_browse=self.browse(cr, uid, ids, context=context)[0]
        if sol_browse.mrp_production_id or sol_browse.use_accounting_qty:
           raise osv.except_osv('Error','Element in production or yet linked')
           return

        if (sol_browse.product_uom_qty + sol_browse.product_id.linked_accounting_qty) > sol_browse.product_id.accounting_qty:
           # raise error!
           raise osv.except_osv('Error','Cannot use store q.: %s (current) + %s (yet linked) > %s (account q.)'%(sol_browse.product_uom_qty, sol_browse.product_id.linked_accounting_qty, sol_browse.product_id.accounting_qty))
        else:
           res=self.write(cr, uid, ids, {'use_accounting_qty':True}, context=context)
        return True

    # Fields function 
    # Get selection value from related:
    def get_supply_method(self, cr, uid, context=None):
        return self.pool.get('product.template')._columns[
            'supply_method'].selection           
    def get_order_state(self, cr, uid, context=None):
        return self.pool.get('sale.order')._columns['state'].selection
       
    _columns = {
        # TODO remove (moved in mx_sale:
        'date_deadline': fields.date('Deadline'),
        'date_delivery':fields.related(
            'order_id', 'date_delivery', type='date', string='Date delivery'),
        #'product_ul_id':fields.many2one('product.ul', 'Required package', required=False, ondelete='set null'),
        # TODO remove ^^^^^^^^^^^^^^^^^^

        'partner_id': fields.related('order_id', 'partner_id', type='many2one', 
            relation='res.partner', string='Partner', store=True),
        'duelist_exposition': fields.related('partner_id', 
            'duelist_exposition', type='boolean', string='Exposed', 
            store=False),

        'to_produce': fields.boolean('To produce', required=False, 
            help="During order importation test if the order line active has product that need to be produced"),
        'use_accounting_qty': fields.boolean('Use accounting qty', 
            help="Set the line to be carried on with store quantity present in accounting store"),
        'supply_method': fields.related('product_id', 'supply_method', 
            type='selection', selection=get_supply_method,
            string='Supply method', 
            store=False),

        'production_line': fields.boolean('Is for production', required=False),
        'mrp_production_id': fields.many2one('mrp.production', 
            'Production order', required=False, ondelete='set null'),
        'accounting_qty': fields.related('product_id','accounting_qty', 
            type='float',  digits=(16, 3), string='Accounting Q.ty', 
            store=False),
        'state_info': fields.related('mrp_production_id', 'state_info', 
            type="char", string="Production info", store=False),
        'accounting_order': fields.related('order_id', 'accounting_order', 
            type="boolean", string="Accounting order", store=True, 
            help="Temporary line from accounting, when order is close it is deleted from OpenERP"),

        'qty_available': fields.related('product_id', 'qty_available', 
            type='float', string='Qty available', store=False),
        'virtual_available': fields.related('product_id', 'virtual_available', 
            type='float', string='Virtual available', store=False),

        'order_state': fields.related('order_id', 'state', type='selection', 
            selection=get_order_state, string='order state', store=False),
        }
    
    _defaults = {
        'to_produce': lambda *a: True,
        }

class mrp_production_material(osv.osv):
    ''' Create object mrp.production.material seems the bom explosed on product
        quantity used as a model for bom list
        This object is use also for mrp.production.workcenter.line only for keep
        the list of fields instead of create another object
    '''
    _name = "mrp.production.material"
    _description= "Production used material"
    _rec_name = "product_id"

    _columns = {
        'product_id':fields.many2one('product.product', 'Product', required=True),
        'quantity': fields.float('Quantity', digits=(16, 2)),
        'uom_id': fields.related('product_id','uom_id', type='many2one', relation='product.uom', string='UOM'),
        'mrp_production_id':fields.many2one('mrp.production', 'Production order', ondelete="cascade", required=False),        # Link if used mrp.production object
        'workcenter_production_id':fields.many2one('mrp.production.workcenter.line', 'Lavoration', ondelete="cascade", required=False), # Link if used mrp.production.workcenter.line object
        'accounting_qty': fields.related('product_id','accounting_qty', type='float',  digits=(16, 3), string='Accounting Q.ty', store=False),
        }

class mrp_production_workcenter_load(osv.osv):
    ''' Load (more than one for workcenter)
    '''
    _name = 'mrp.production.workcenter.load'
    _description = 'Workcenter load'
    _rec_name = 'date'
    _order = 'sequence,date'

    # Override method:
    def create(self, cr, uid, vals, context=None):
        """
        Add sequence during creation of new load:
        @param cr: cursor to database
        @param user: id of current user
        @param vals: provides a data for new record
        @param context: context arguments, like lang, time zone

        @return: returns a id of new record
        """
        last = 0
        wc_id = vals.get('line_id', False)
        if wc_id: # mandatory
            wc_pool = self.pool.get('mrp.production.workcenter.line')
            for lavoration in wc_pool.browse(cr, uid, wc_id, context=context).production_id.workcenter_lines:
                for load in lavoration.load_ids:
                    if last < load.sequence:
                        last = load.sequence
        sequence = last + 1
        vals['sequence']=sequence
        res_id = super(mrp_production_workcenter_load, self).create(cr, uid, vals, context=context)
        return res_id

    _columns = {
        #'name': fields.char('Name',),
        'date': fields.datetime('Date', help="Operation date", required=True),
        'product_qty': fields.float('Quantity', digits=(16, 6), required=True),
        'product_code': fields.char('Product code', size=64, required=False, 
            readonly=False, 
            help="Long code for product: product - lavoration - package - ecc. (used for traceability)"),
        'partial': fields.boolean('Partial'),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'line_id': fields.many2one('mrp.production.workcenter.line', 'Workcenter line', required=True),

        'package_id':fields.many2one('product.ul', 'Package', required=False),
        'ul_qty': fields.integer('Package q.', help="Package quantity to unload from accounting"),

        'pallet_product_id':fields.many2one('product.product', 'Pallet', required=False),
        'pallet_qty': fields.integer('Pallet q.', help="Pallet quantity to unload for accounting"),

        # Information linked with accounting program:
        'accounting_cl_code': fields.char(
            'Accounting CL code',
            size=8,
            required=False,
            readonly=False,
            help="Code of CL assigned during importation in accounting program (for link the document)",),
        'accounting_cost': fields.float('Cost from material', digits=(16, 6), required=False),
        'accounting_cost_confirmed': fields.boolean('Cost confirmed', required=False),

        'recycle': fields.boolean('Recycle', required=False, help="Recycle product"),
        'recycle_product_id': fields.many2one('product.product', 'Product', required=False),

        'wrong':fields.boolean('Wrong', required=False, help="Wrong product, coded with a standard code"),
        'wrong_comment': fields.text('Wrong comment'),

        'sequence': fields.integer('Seq. n.'),
        'production_id': fields.related('line_id', 'production_id', type='many2one', relation='mrp.production', string='Production', store=True),
        'product_id': fields.related('line_id', 'product', type='many2one', relation='product.product', string='Product', store=True),
        'workcenter_line_id': fields.related('line_id', 'workcenter_id', type='many2one', relation='mrp.workcenter', string='Line', store=True),
        }

    _defaults={
        'date': lambda *x: datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': lambda obj, cr, uid, context: uid,
        'sequence': lambda *x: 0,
        'accounting_cost_confirmed': lambda *x: False,
        }

class mrp_workcenter_history(osv.osv):
    ''' History of lavoration caracteristic for product-workcenter link
    '''
    _name = 'mrp.workcenter.history'
    _description = 'Workcenter histroy'
    _rec_name = 'workcenter_id'
    _order='product_id'

    _columns = {
        'date': fields.datetime('Date', help="Operation date", required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'workcenter_id': fields.many2one('mrp.workcenter', 'Workcenter', required=True),
        'single_cycle_duration': fields.float('Cycle duration', digits=(8, 3), required=False, help="Duration time for one cycle"),
        'single_cycle_qty': fields.float('Cycle quantity', digits=(8, 3), required=False, help="Production quantity for one cycle"),
        # Parameter:
        'parameter_note':fields.text('Parameter note', required=False, readonly=False),

        #  E energo     S lubrificanti polvere
        'parameter_hammer':fields.char('Hammers', size=15, required=False, readonly=False),
        'parameter_grid':fields.char('Grid', size=15, required=False, readonly=False),
        'parameter_speed':fields.char('Speed m/s', size=15, required=False, readonly=False),
        'parameter_temperature':fields.char('Temperature', size=15, required=False, readonly=False), # also G grassi    O oli      F fosfatanti

        #  X panflux    N sali
        'parameter_time_misc': fields.float('Time misc.', digits=(8, 3), required=False, help="Time for misc."), # also G grassi    O oli      F fosfatanti
        }

    _defaults={
        'date': lambda *x: datetime.now().strftime(
            DEFAULT_SERVER_DATETIME_FORMAT),
        }

# Not work!!
"""class resource_resource(osv.osv):
    ''' Class where inherits mrp.workcenter (changing order)
    '''
    _name = "resource.resource"
    _inherit = "resource.resource"
    _order = "name"
resource_resource()"""

class mrp_workcenter(osv.osv):
    ''' Add 2many elements in mrp.workcenter
    '''
    _name = 'mrp.workcenter'
    _inherit = 'mrp.workcenter'

    _columns = {
        'history_lavoration_ids': fields.one2many('mrp.workcenter.history', 'workcenter_id', 'Lavoration history', required=False),
        'hour_daily_work': fields.float('Daily work hours', digits=(8,2), required=False, help="Usual working hour per day for this line"),
        'cost_product_id': fields.many2one('product.product', 'Product linked', required=False, help='Product linked to the line for cost computation'),
        'parent_workcenter_id': fields.many2one('mrp.workcenter', 'Parent workcenter', required=False, help='Parent workcenter line, used for put history elements (not for lavoration cost that are linked to line)'),
        }
    _defaults = {
        'hour_daily_work': lambda *x: 16, # default working hour
        }

class mrp_production_workcenter_line_extra(osv.osv):
    ''' Update some _defaults value
    '''
    _name = 'mrp.production.workcenter.line'
    _inherit = 'mrp.production.workcenter.line'

    def add_hour(self, from_datetime, hours):
        ''' Add to datetime element the hour in format float and return result
        '''
        try:
            res = (datetime.strptime(from_datetime, "%Y-%m-%d %H:%M:%S") + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
            return res
        except:
            return False # raise error?

    # -------------
    # Override ORM:
    # -------------
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False):
        """
        Return a view and fields for current model. where view will be depends on {view_type}.
        @param cr: cursor to database
        @param uid: id of current user
        @param view_id: list of fields, which required to read signatures
        @param view_type: defines a view type. it can be one of (form, tree, graph, calender, gantt, search, mdx)
        @param context: context arguments, like lang, time zone
        @param toolbar: contains a list of reports, wizards, and links related to current model
        
        @return: returns a dict that contains definition for fields, views, and toolbars
        """        
        if view_type == 'form' and no_establishment_group(self, cr, uid, context=context):
            toolbar = False
        return super(mrp_production_workcenter_line_extra, self).fields_view_get(
            cr, uid, view_id, view_type, context=context, toolbar=toolbar)

    # -------------
    # Button event:
    # -------------
    def date_start_now(self, cr, uid, ids, context=None):
        ''' Set data start to now
        '''
        return self.write(cr, uid, ids, {'date_start': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)

    def date_stop_now(self, cr, uid, ids, context=None):
        ''' Set data stop to now
        '''

        now = datetime.now()
        try:
            lavoration_proxy = self.browse(cr, uid, ids, context=context)[0]
            delay = now - datetime.strptime(lavoration_proxy.date_start, DEFAULT_SERVER_DATETIME_FORMAT)
            delay = delay.seconds / 3600.0

        except:
            delay = 0.0

        return self.write(
            cr,
            uid,
            ids,
            {
                'date_finished': now.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                'delay': delay,
            },
            context=context)

    def load_materials_from_bom(self, cr, uid, ids, context=None):
        ''' Create bom lined reloading elements
        '''
        return self._create_bom_lines(cr, uid, ids[0], context=context)

    def load_materials_from_production(self, cr, uid, ids, context=None):
        ''' Create lined from production elements
        '''
        return self._create_bom_lines(cr, uid, ids[0], from_production=True, context=context)

    # ------------------
    # Onchange function:
    # ------------------
    def onchange_workcenter_load_cycle(self, cr, uid, ids, product, workcenter_id, real_date_planned,cycle,context=None):
        ''' Changing workcenter load hour values and reset all totals
        '''
        res = {'value': {}}

        if product and workcenter_id:
            # test if there's a parent (if so read there the history)
            wc_proxy = self.pool.get('mrp.workcenter').browse(cr, uid, workcenter_id, context=context)
            if wc_proxy.parent_workcenter_id:
                workcenter_id = wc_proxy.parent_workcenter_id.id
            
            history_pool = self.pool.get('mrp.workcenter.history')
            item_ids = history_pool.search(cr, uid, [
                ('product_id', '=', product),
                ('workcenter_id', '=', workcenter_id)])
            if item_ids:
                history_proxy=history_pool.browse(cr, uid, item_ids)[0]
                res['value']['cycle'] = cycle if cycle else 1
                res['value']['single_cycle_duration'] = history_proxy.single_cycle_duration
                res['value']['single_cycle_qty'] = history_proxy.single_cycle_qty
                res['force_cycle_default'] = False
                if real_date_planned:
                    res['value']['real_date_planned_end'] = self.add_hour(real_date_planned, history_proxy.single_cycle_duration)

                # Warning message because totals are reset and hourly are loaded from history:
                res['warning'] = {
                    'title': _('Information:'),
                    'message': _('Loaded default hourly parameters workcenter-product, maybe totals are changed!'),
                }
        return res

    def onchange_cycle_values(self, cr, uid, ids, cycle, single_cycle_duration, single_cycle_qty, real_date_planned, hour, product_qty, context=None):#, mode='value', context=None):
        ''' On change cycle parameters (one function for all elements for loop
            problems.
            self: obj instance
            cr: database cursor
            uid: user id
            ids: list of object (usually one)
            cycle: number of cycle
            single_cycle_duration: single cycle duration
            single_cycle_qty: single cycle quantity
            real_date_planned: real date planned (for calculate term of lavoration)
            hour: total hour duration
            product_qty: total quantity of production
            #mode: mode for onchange call 3 type: 
            #    value (first 3 field variation,
            #    hour (total hour variation)
            #    quantity (total quantity variation)                  
            context: context dict
        '''
        res = {'value': {}}
        if not cycle:
            return res
            #cycle == 1.0
            #res['value']['cycle'] = cycle
            
        hour = 0.0
        if single_cycle_duration:
            hour = cycle * float(single_cycle_duration)
            res['value']['hour'] = cycle * float(single_cycle_duration)
        if single_cycle_qty:
            res['value']['product_qty'] = cycle * float(single_cycle_qty)

        if real_date_planned:
            res['value']['real_date_planned_end'] = self.add_hour(
                real_date_planned, 
                hour,
            )
        return res

    def cycle_historyzation(self, cr, uid, vals, context=None):
         ''' Update or create record in history of lavoration
             (workcenter-product parameters)
         '''
         try:
             history_pool = self.pool.get('mrp.workcenter.history')
             production_pool = self.pool.get('mrp.production')
             
             production_id = vals.get('production_id',False)
             workcenter_id = vals.get('workcenter_id',False)
             
             # Test if workcenbter is child (if so take parent for save hist.)
             wc_proxy = self.pool.get('mrp.workcenter').browse(cr, uid, workcenter_id, context=context)
             if wc_proxy.parent_workcenter_id:
                 workcenter_id = wc_proxy.parent_workcenter_id.id
                 
             if not production_id:
                 return False # error
             product_id = production_pool.browse(cr, uid, production_id, context=context).product_id.id

             data = {
                 'product_id': product_id,
                 'workcenter_id': workcenter_id,
                 'single_cycle_duration': vals.get('single_cycle_duration',False),
                 'single_cycle_qty': vals.get('single_cycle_qty',False),
             }

             item_ids = history_pool.search(cr, uid, [
                 ('product_id', '=', product_id),
                 ('workcenter_id', '=', workcenter_id),
             ], context=context)

             if item_ids:
                 res = history_pool.write(cr, uid, item_ids, data, context=context)
             else:
                 res_id = history_pool.create(cr, uid, data, context=context)
         except:
             return False # manage error?
         return True

    # -----------------
    # Utility function:
    # -----------------
    def _create_bom_lines(self, cr, uid, lavoration_id, from_production=False, context=None):
        ''' Create a BOM list for the passed lavoration
            Actual items will be deleted and reloaded with quantity passed
        '''
        lavoration_browse = self.browse(cr, uid, lavoration_id, context=context)
        try:
            if not lavoration_browse.production_id.bom_id and not lavoration_browse.product_qty:
                return False # TODO raise error

            # Delete all elements:
            material_pool = self.pool.get('mrp.production.material')
            material_ids = material_pool.search(cr, uid, [('workcenter_production_id','=', lavoration_id)], context=context)
            material_pool.unlink(cr, uid, material_ids, context=context)

            # Create elements from bom:
            if from_production:
                for element in lavoration_browse.production_id.bom_material_ids:
                    material_pool.create(cr, uid, {
                        'product_id': element.product_id.id,
                        'quantity': element.quantity / lavoration_browse.production_id.product_qty * lavoration_browse.product_qty if lavoration_browse.production_id.product_qty else 0.0,
                        'uom_id': element.product_id.uom_id.id,
                        'workcenter_production_id': lavoration_id,
                    }, context=context)
            else:
                for element in lavoration_browse.production_id.bom_id.bom_lines:
                    material_pool.create(cr, uid, {
                        'product_id': element.product_id.id,
                        'quantity': element.product_qty * lavoration_browse.product_qty / lavoration_browse.production_id.bom_id.product_qty if lavoration_browse.production_id.bom_id.product_qty else 0.0,
                        'uom_id': element.product_id.uom_id.id,
                        'workcenter_production_id': lavoration_id,
                    }, context=context)
        except:
            return False
        return True


    # ------------------
    # Override function:
    # ------------------
    # >>> ORM Function:
    def create(self, cr, uid, vals, context=None):
        """ Override create method only for generare BOM materials in subfield
            bom_materials_ids, initially is a copy of mrp.production ones
        """
        vals['real_date_planned_end'] = self.add_hour(vals.get('real_date_planned',False), vals.get('hour',False))
        if vals.get('force_cycle_default', False):
            res = self.cycle_historyzation(cr, uid, vals, context=context)
            vals['force_cycle_default'] = False # after historization force return False

        res_id = super(mrp_production_workcenter_line_extra, self).create(cr, uid, vals, context=context)
        if res_id: # Create bom for this lavoration: (only during creations)!! # TODO test if is it is not created (or block qty if present)?
            production_order_browse=self.pool.get('mrp.production').browse(cr, uid, [vals.get('production_id',0)], context=context)[0]
            for item in production_order_browse.bom_material_ids:
                # proportionally created on total production order and total lavoration order
                item_id=self.pool.get("mrp.production.material").create(cr, uid, {
                    'product_id': item.product_id.id,
                    'quantity': item.quantity * vals.get('product_qty',0.0) / production_order_browse.product_qty if production_order_browse.product_qty else 0.0,
                    'workcenter_production_id': res_id, # current yet created WC line
                }, context=context)
        return res_id

    def write(self, cr, uid, ids, vals, context=None, update=False):
        """ Test if must history the parameters for cycle lavoration of
            product-workcenter
        """
        wk_proxy=self.browse(cr, uid, ids, context=context)[0] # for load missing values:
        if vals.get('real_date_planned',False) or vals.get('hour',False):
            vals['real_date_planned_end'] = self.add_hour(vals.get('real_date_planned',wk_proxy.real_date_planned), vals.get('hour',wk_proxy.hour))

        if vals.get('force_cycle_default', False): # must save parameters for lavoration product-line
            # Update value if not present in write operation:
            vals['workcenter_id'] = vals.get('workcenter_id', wk_proxy.workcenter_id.id)
            vals['production_id'] = vals.get('production_id', wk_proxy.production_id.id) # TODO for get product_id jumping on production_id
            vals['single_cycle_duration'] = vals.get('single_cycle_duration', wk_proxy.single_cycle_duration)
            vals['single_cycle_qty'] = vals.get('single_cycle_qty', wk_proxy.single_cycle_qty)
            vals['force_cycle_default'] = False # Return to false because the update operation is done!
            update = self.cycle_historyzation(cr, uid, vals, context=context) # Update history of product-workcenter
        return super(mrp_production_workcenter_line_extra, self).write(cr, uid, ids, vals, context=context, update=False)

        """#TODO: process before updating resource
        real_date_planned=vals.get('real_date_planned', False)
        if real_date_planned:
            # if planned date is change:
            # 1. not go over planned delivery order
            for lavoration in self.browse(cr, uid, ids, context=context):
                for order_line in lavoration.production_id.order_line_ids:
                    if order_line.order_id.state=='planned':
                        if real_date_planned > order_line.order_id.date_delivery: # mandatory
                            raise osv.except_osv(_('Error!'), _("There's one order with planned delivery date [%s - %s]!"%(order_line.order_id.name, order_line.order_id.date_delivery)))

            # 2. test state if can moved
        res = super(mrp_production_workcenter_line_extra, self).write(cr, user, ids, vals, context)
        return res"""

    # ---------------------------
    # Workflow activity function:
    # ---------------------------
    def modify_production_order_state(self, cr, uid, ids, action, context=None):
        """ Modifies production order state if work order state is changed.
        @param action: Action to perform.
        @return: Nothing
        """
        lavoration_proxy=self.browse(cr, uid, ids, context=context)[0]
        if action=="start":
            self.pool.get("mrp.production").action_auto_status_depends_on_lavoration(cr, uid, [lavoration_proxy.production_id.id], action, context=context)
        return True

    """def action_start_working(self, cr, uid, ids, context=None):
        ''' Override start method to update real product qty
        '''
        result = super(mrp_production_workcenter_line_extra, self).action_start_working(cr, uid, ids, context=context)
        lavoration_browse=self.browse(cr, uid, ids, context=context)[0]

        self.write(cr, uid, ids, {'real_product_qty': lavoration_browse.product_qty,}, context=context)
        return True"""

    #def get_name_from_production(self, cr, uid, context=None):
    #    ''' Return a name depend on production and sequence
    #    '''
    #    if context.get('default_production_id',False):
    #        production_browse=self.pool.get('mrp.production').browse(cr, uid, context.get('default_production_id',0), context=context)
    #        try:
    #            next = 1 + max([item.sequence for item in production_browse.workcenter_lines])
    #        except:
    #            next = 1
    #
    #        return "%s#%0000d"%(production_browse.name, next)
    #    return False

    # Function fields:
    # Vedere se è necessario inserire il campo o è meglio farlo con onchange
    #def _function_hours_day_line(self, cr, uid, ids, fields, param, context=None):
    #    ''' Total of hour a day for lavoration
    #    '''
    #    res={}
    #    self.search(cr, uid, [()], context=context)
    #    for item in self.browse(cr, uid, ids, context=context):
    #        try:
    #            res[item.id]=item.order_id.accounting_state=="planned"
    #        except:
    #            res[item.id]=False
    #    return res

    _columns = {
        'bom_material_ids':fields.one2many('mrp.production.material', 'workcenter_production_id', 'BOM material lines', required=False),
        'product_qty': fields.float('Quantity', digits=(16, 6), required=True),
        'real_product_qty': fields.float('Real quantity', digits=(16, 6), required=True, help="This value will be create in accounting as a CL of product"), # TODO trasferire totale nella produzione
        'lavoration_note': fields.text('Lavoration note'),
        'anomalie_note': fields.text('Anomalies'),
        #'lavoration_number': fields.char('Lavoration ID', size=16, required=False, help="ID for traceability of the lavoration"),
        'accounting_sl_code': fields.char('Accounting SL code', size=8, help="Code of SL assigned during importation in accounting program (material and package)"),

        #NOTE: used other date for planning element because original date_planned and date_planned_end are update from mrp.production
        'real_date_planned': fields.datetime('Date planned', help = "Real date planned for scheduling operation", required = True),
        'real_date_planned_end': fields.datetime('Date planned end', help = "Real date planned end for scheduling operation"),

        'single_cycle_duration': fields.float('Cycle duration', digits=(8, 3), required=False, help="Duration time for one cycle"),
        'single_cycle_qty': fields.float('Cycle quantity', digits=(8, 3), required=False, help="Production quantity for one cycle"),
        'force_cycle_default': fields.boolean('Force as default parameters', help="Save this parameter for product cycle in this line as default, next lavoration start with this hour cycle values!"),
        'load_ids': fields.one2many('mrp.production.workcenter.load', 'line_id', 'Load'),
        'unload_confirmed': fields.boolean('Unload confirmed', help="All material in list are confirmed!"),
        'load_confirmed': fields.boolean('Load confirmed', help="All list of unload is confirmed!"),          # TODO togliere quando è spostato alla produzione
        'material_from_production': fields.boolean('Material from production', 
            help="Materials are loaded from production document, instead from product bom."),
        'max_hour_day': fields.float('Max hour a day', digits=(5, 3),
            help='Max hour for daily work'),

        #'hours_day_line': fields.function(_function_hours_day_line, method=True, type='float', string='Hours day line', store=False),
        #'unload_confirmed': fields.boolean('Unload confirmed', help="All list of unload is confirmed!"),
    }

    _defaults = {
        #'name': lambda s, c, uid, ctx: s.get_name_from_production(c, uid, context=ctx),
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'wcline.number'),
        'cycle': lambda *a: 1,
        'hour': lambda *a: 4,
        'real_date_planned': lambda *x: datetime.today().strftime("%Y-%m-%d 06:00:00"),#  "%s 08:00:00"%(ctx.get('date', fields.date.context_today(self,cr,uid,context=ctx))),
        'material_from_production': lambda *x: False,
        #'load_confirmed': lambda *a: False,

        #'lavoration_number': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'wcline.number'),
        #'unload_confirmed': lambda *a: False,
        #'real_date_planned_end': lambda *x: False,
        #'bom_material_ids': lambda s, cr, uid, ctx: s.create_bom_elements_from_production(cr, uid, context=ctx),
    }

class mrp_production_package(osv.osv):
    ''' Package to use for production
    '''
    _name="mrp.production.package"
    _description = 'Production package'
    _rec_name = 'partner_id'
    
    _columns = {
        'production_id':fields.many2one('mrp.production', 'Production', required=False, ondelete='cascade', ),
        'product_ul_id':fields.many2one('product.ul', 'Required package', required=False, ondelete='set null', ),
        'partner_id':fields.many2one('res.partner', 'Customer', required=False, ondelete='set null', ),
        'order_line_id':fields.many2one('sale.order.line', 'Sale order line', required=False, ondelete='set null', ),
        'quantity': fields.float('Quantity', digits=(16, 2)),    
        'stock': fields.boolean('Stock', required=False),
    }
    _defaults = {
        'stock': lambda *x: True,
    }
    
class mrp_production_extra(osv.osv):
    ''' Create extra fields in mrp.production obj
    '''
    _name = "mrp.production"
    _inherit = ["mrp.production", 'mail.thread']

    # -----------------
    # Utility function:
    # -----------------
    def action_auto_status_depends_on_lavoration(self, cr, uid, ids, actual_action, context=None):
        ''' Test status of workcenter, generate mrp.production accounting_state
            depending on it
        '''
        # TODO do it better for close evaluations
        wf_service = netsvc.LocalService("workflow")
        #production_browse=self.browse(cr, uid, ids, context=context)[0]
        if actual_action=="start":
            #if production_browse.accounting_state=='draft':
            # test if there's one workcenter not in draft (so production this)
            #for item in production_browse.workcenter_lines:
            #     if item.state not in ("draft", "cancel"):
            wf_service.trg_validate(uid, 'mrp.production', ids[0], 'trigger_accounting_production', cr)
            #         break
        return True

    def _action_load_materials_from_bom(self, cr, uid, item_id, context=None):
        ''' Generic function called from create elements or button for load
            sub material according to BOM selected and quantity
            item_id is the id of mrp.production (integer not list)
            This material is only for see store status, non used for lavorations
        '''
        production_browse = self.browse(cr, uid, item_id, context=context)
        if not production_browse.bom_id and not production_browse.product_qty:
            return True # TODO raise error

        # Delete all elements:
        material_pool=self.pool.get('mrp.production.material')
        material_ids=material_pool.search(cr, uid, [('mrp_production_id','=',item_id)], context=context)
        material_pool.unlink(cr, uid, material_ids, context=context)

        # Create elements from bom:
        table = _("<tr><td>Product</td><td>Q.</td></tr>")
        for element in production_browse.bom_id.bom_lines:
            quantity = element.product_qty * production_browse.product_qty / production_browse.bom_id.product_qty if production_browse.bom_id.product_qty else 0.0
            material_pool.create(cr, uid, {
                'product_id': element.product_id.id,
                'quantity': quantity,
                'uom_id': element.product_id.uom_id.id,
                'mrp_production_id': item_id,
            }, context=context)
            table += "<tr><td>[%s] %s</td><td>%s %s</td></tr>" % (
                element.product_id.default_code or '',
                element.product_id.name or _('Unknown'),
                quantity,
                element.product_id.uom_id.name,
                )
        
        self.write_thread_message(
            cr, uid, [item_id], 
            subject=_('Load BOM elements:'), 
            body=_('<table class="oe_list_content">%s</table>') % table,
            context=context)            
        return True

    # ----------
    # On change:
    # ----------
    def on_change_qty_alert(self, cr, uid, ids, context=None):
        ''' Return alert message
        '''
        return {'warning': {
            'title': _('Alert'),
            'message': _(
                'Remember to regenerate BOM elements with botton '
                '"Load from BOM" after change quantity!')}}

    # -------------
    # Event button:
    # -------------
    def dummy_refresh(self, cr, uid, ids, context=None):
        ''' Dummy refresh (simple pression of button)
        '''
        return True
        
    # ----------------
    # Workflow action:
    # ----------------
    def production_accounting_draft(self, cr, uid, ids, context=None):
        ''' Draft
        '''
        self.write(cr, uid, ids, {'accounting_state':'draft'}, context=context)
        self.write_object_change_state(cr, uid, ids, state='accounting_state', context=context)
        return True

    def production_accounting_open(self, cr, uid, ids, context=None):
        ''' Open
        '''
        self.write(cr, uid, ids, {'accounting_state':'production'}, context=context)
        self.write_object_change_state(cr, uid, ids, state='accounting_state', context=context)
        return True

    def production_accounting_close(self, cr, uid, ids, context=None):
        ''' Close
        '''
        self.write(cr, uid, ids, {'accounting_state':'close'}, context=context)
        self.write_object_change_state(cr, uid, ids, state='accounting_state', context=context)
        return True

    def production_accounting_cancel(self, cr, uid, ids, context=None):
        ''' Cancel
        '''
        self.write(cr, uid, ids, {'accounting_state':'cancel'}, context=context)
        self.write_object_change_state(cr, uid, ids, state='accounting_state', context=context)
        return True

    def load_materials_from_bom(self, cr, uid, ids, context=None):
        ''' Change list of element according to weight and bom
        '''
        return self._action_load_materials_from_bom(cr, uid, ids[0], context=context)

    # ----------------
    # Function fields:
    # ----------------
    def _function_lavoration_planned(self, cr, uid, ids, field, args, context=None):
        """ Check and return total planned lavoration and boolean if it is all
            planned
        """
        res = {}
        for production in self.browse(cr, uid, ids, context=context):
            res[production.id] = {}
            res[production.id]['lavoration_planned'] = 0.0
            res[production.id]['lavoration_all_planned'] = False
            res[production.id]['total_production_loaded'] = 0.0
            
            #res[production.id]['state_info']=""
            min_date = False
            max_date = False

            for lavoration in production.workcenter_lines:
                if lavoration.real_date_planned: # TODO remove!
                    if not min_date or lavoration.real_date_planned[:10] < min_date:
                        min_date=lavoration.real_date_planned[:10]
                    if not max_date or lavoration.real_date_planned[:10] > max_date:
                        max_date=lavoration.real_date_planned[:10]
                res[production.id]['lavoration_planned'] += lavoration.product_qty or 0.0
                for load in lavoration.load_ids:
                    res[production.id]['total_production_loaded'] += load.product_qty

            if res[production.id]['lavoration_planned'] >= production.product_qty:
                res[production.id]['lavoration_all_planned'] = True

            this_year = datetime.now().strftime("%Y")
            if min_date:
                min_date_text = "%s/%s" % (
                    min_date[8:10], 
                    min_date[5:7]) if min_date[:4] == this_year else "%s/%s/%s" % (
                        min_date[8:10], 
                        min_date[5:7], 
                        min_date[:4])
            else:
                min_date_text = "?"
            if max_date:
                max_date_text = "%s/%s" % (
                    max_date[8:10], 
                    max_date[5:7]) if max_date[:4] == this_year else "%s/%s/%s" % (
                        max_date[8:10], 
                        max_date[5:7], 
                        max_date[:4])
            else:
                max_date_text = "?"

            range_date= "[%s-%s]" % (min_date_text, max_date_text)
            res[production.id]['state_info'] = "%s\n%s" % (
                _("All planned: %6.0f") % (
                    res[production.id]['lavoration_planned'], ) if res[production.id]['lavoration_all_planned'] else "%6.0f / %6.0f" % (
                        res[production.id]['lavoration_planned'], 
                        production.product_qty), 
                        range_date,
            )
        return res
    
    def _function_total_material(self, cr, uid, ids, field, args, context=None):
        ''' Extra information about materials used (totals for check) 
        '''
        res = {}
        for production in self.browse(cr, uid, ids, context=context):
            res[production.id] = {}
            res[production.id]['total_production_material'] = 0.0
            for material in production.bom_material_ids:
                res[production.id]['total_production_material'] += material.quantity
            res[production.id]['total_production_material_anomaly'] = not (res[production.id]['total_production_material'] == production.product_qty)
        return res

    _columns = {
        'order_lines_ids': fields.one2many(
            'sale.order.line', 'mrp_production_id', 'Order lines', 
            required=False),#write=['base.group_sale_manager'], read=['base.group_user','base.group_sale_salesman']),
        'bom_material_ids': fields.one2many(
            'mrp.production.material', 'mrp_production_id', 
            'BOM material lines', required=False),
        'package_ids': fields.one2many(
            'mrp.production.package', 'production_id', 'Package', 
            required=False),
        'load_ids': fields.one2many(
            'mrp.production.workcenter.load', 
            'production_id', 'Loads', required=False),
        'accounting_qty': fields.related(
            'product_id','accounting_qty', type='float', 
            digits=(16, 3), string='Accounting Q.ty', store=False),

        # Total quantity values:
        'lavoration_planned': fields.function(
            _function_lavoration_planned, method=True, type='float', 
            string='Lavoration planned', store=False, multi='planned'),
        'lavoration_all_planned': fields.function(
            _function_lavoration_planned, method=True, type='boolean', 
            string='Is all planned', store=True, multi='planned'),
        'state_info': fields.function(
            _function_lavoration_planned, method=True, type='char', 
            size=30, string='State info', store=False, multi='planned'),
        'total_production_loaded': fields.function(
            _function_lavoration_planned, method=True, type='float', 
            digit=(16, 3), string='Total loaded', store=False, 
            multi='planned'),
        
        'total_production_material': fields.function(
            _function_total_material, method=True, type='float', 
            digit=(16, 3), string='Total material', store=False, 
            multi='material'),
        'total_production_material_anomaly': fields.function(
            _function_total_material, method=True, type='boolean', 
            string='Material anomaly', store=False, multi='material'),
        
        # Workflow:
        'accounting_state':fields.selection([
               ('draft','Draft'),
               ('production','In production'),
               ('close','Close'),
               ('cancel','Cancel'),
        ],'Accounting state', select=True, readonly=True),
    }
    _defaults = {
        'accounting_state': lambda *a: 'draft',
    }

class sale_order_line_extra(osv.osv):
    ''' Extra fields
        Insert overrider function for log production
    '''
    _name="sale.order.line"
    _inherit="sale.order.line"

    #def create(self, cr, uid, vals, context=None):
    #    """
    #    Create a new record for a model ModelName
    #    @param cr: cursor to database
    #    @param uid: id of current user
    #    @param vals: provides a data for new record
    #    @param context: context arguments, like lang, time zone
    #    
    #    @return: returns a id of new record
    #    """
    #    res_id = super(sale_order_line_extra, self).create(cr, uid, vals, context=context)
    #    return res_id
    
    def write(self, cr, uid, ids, vals, context=None):
        """
        Update redord(s) comes in {ids}, with new value comes as {vals}
        return True on success, False otherwise
    
        @param cr: cursor to database
        @param uid: id of current user
        @param ids: list of record ids to be update
        @param vals: dict of new values to be set
        @param context: context arguments, like lang, time zone
        
        @return: True on success, False otherwise
        """
        # Log the assignement to Production order:
        if ids and 'mrp_production_id' in vals:
            mrp_production_id = vals.get('mrp_production_id', False)
            if type(ids) not in (list, tuple):
                ids = [ids]
                
            body = ""            
            subject = _('Assignement order lines:')
            for line in self.browse(cr, uid, ids, context=context):
                if not mrp_production_id: # unlink line from mrp case:
                    mrp_production_id = line.mrp_production_id.id
                    subject = _('Removed order lines:')
                    
                body += _("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>") % (
                    line.order_id.name, 
                    line.product_id.default_code, 
                    line.product_uom_qty,
                    line.date_deadline,
                    )
            self.pool.get('mrp.production').write_thread_message(
                cr, uid, [mrp_production_id], 
                subject = subject, 
                body = _("<table class='oe_list_content'><tr><td>Order</td>"
                    "<td>Product</td><td>Q.</td><td>Deadline</td></tr>"
                    "%s</table>") % body,
                    context=context)

        res = super(sale_order_line_extra, self).write(cr, uid, ids, vals, context)
        return res
    
    def unlink(self, cr, uid, ids, context=None):
        """
        Delete all record(s) from table heaving record id in ids
        return True on success, False otherwise 
    
        @param cr: cursor to database
        @param uid: id of current user
        @param ids: list of record ids to be removed from table
        @param context: context arguments, like lang, time zone
        
        @return: True on success, False otherwise
        """
        if type(ids) not in (tuple, list): # for int values of ids
            ids = [ids]

        mrp_pool = self.pool.get('mrp.production')
        for line in self.browse(cr, uid, ids, context=context):
            if line.mrp_production_id: # production linked
                mrp_pool.write_thread_message(
                    cr, uid, [line.mrp_production_id.id], 
                    subject = _("Order line delivery / deleted"), 
                    body = _("Order: %s [%s] q.: %s (deadline: %s)") % (
                        line.order_id.name, 
                        line.product_id.default_code, 
                        line.product_uom_qty,
                        line.date_deadline,
                        ), context=context)
        
        res = super(sale_order_line_extra, self).unlink(cr, uid, ids, context)
        return res
        
    def _function_get_mandatory_delivery(self, cr, uid, ids, fields, param, context = None):
        ''' Test if oc header has delivery status setted
        '''
        res = {}
        for item in self.browse(cr, uid, ids, context = context):
            try:
                res[item.id] = item.order_id.accounting_state == "planned"
            except:
                res[item.id] = False
        return res

    _columns = {
        'state_info': fields.related('mrp_production_id', 'state_info', type="char", string="Production info", store = False),

        'previous_product_qty': fields.float('Previous quantity', digits=(16, 6), required=False, help="Save last modified value if Q. is changed"),
        'previous_product_id': fields.many2one('product.product', 'Previous product', required=False, help="Save last modified product_id if changed"),
        'mandatory_delivery': fields.function(
            _function_get_mandatory_delivery, method=True, type='boolean', 
            string='Mandatory delivery', store=False),
        'accounting_state': fields.selection([
            ('not','Not Confirmed'), # Not confirmed (first step during importation)
            ('new','New'),           # Confirmed
            ('modified','Modified'), # Quantity only (for production or linked to store)
            ('updated','Updated'), # after new if line is the same
            #('planned','Planned for delivery'),
            ('deleted','Deleted'),              # Not used (order vanished when delete)
            ('close','Close'),                  # Not used (order vanished when delete)
            ],'Accounting state', select=True, readonly=True),
        # TODO Aggiungere campo function per calcolare se la riga può essere evasa!
        # 1 test: verificare se è in produzione e se la produzione risulta chiusa
        # 2 test: verificare se con disponibilità a magazzino (+ produzione effettuata) risulterebbe chiusa
    }
    _defaults = {
        'accounting_state': lambda *x: 'new',
        'previous_product_qty': lambda *x: False,
        'previous_product_id': lambda *x: False,
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
