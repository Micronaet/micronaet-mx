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
import openerp.netsvc
import logging
from openerp.osv import osv, orm, fields
from datetime import datetime, timedelta
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare,
    )
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)

class stock_production_lot_accounting(orm.Model):
    ''' Add extra field for manage status of lot from accounting
    '''
    _name = 'stock.production.lot'
    _inherit = 'stock.production.lot'
    
    # -----------------
    # Scheduled action:
    # -----------------
    def scheduled_import_lot_quantity(self, cr, uid, path, filename, 
            package=True, context=None):
        ''' Scheduled function for import status lot from accounting
            self: this instance
            cr: cursor
            uid: user id            
            path: folder path of csv file
            filename: csv file name
            package: manage package (default False)
        '''
        if context is None:
            context = {}
        separator = ";"

        file_csv = os.path.join(os.path.expanduser(path), filename)
        try:
            f = open(file_csv, 'r')
        except:
            _logger.error("Error accessing file: %s" % file_csv)
            return False
            
        product_pool = self.pool.get("product.product")
        package_pool = self.pool.get("product.ul")
        
        i = 0
        lot_modify_ids = []
        for line in f:
            try:
                i += 1
                line_csv = line.strip().split(separator)
                
                # Fields:
                product_code = line_csv[0].strip()
                lot_code = line_csv[1].strip()
                package_code = line_csv[2].strip()
                stock_available_accounting = float(line_csv[3].strip() or "0")
                accounting_ref = line_csv[4].strip()

                try: # correct format, ex.: 000001
                    lot_code = "%06d" % (int(lot_code), )
                    anomaly = False
                except:
                    anomaly = True    

                if package:
                    package_ids = package_pool.search(cr, uid, [
                        ('code', '=', package_code)], context=context)
                    if package_ids:
                        package_id = package_ids[0]    
                    else: # fast create a package
                        package_id = package_pool.create(cr, uid, {
                            'code': package_code,
                            'name': _("Package: %s") % package_code,
                            'type': 'unit',
                            }, context=context)
                    name = "%s-%s" % (lot_code, package_code)
                else:
                    package_id = False        
                    name = lot_code
                            
                # Get ref by ID of code read
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', product_code)], context=context)
                if not product_ids:
                    _logger.error("Line: %s - Product not found: %s" % (
                            i, product_code))
                    continue

                # Search lot            
                lot_ids = self.search(cr, uid, [
                    ('name', '=', name)], context=context)
                data = {
                    'name': name,
                    'product_id': product_ids[0],
                    'package_id': package_id,
                    'stock_available_accounting': stock_available_accounting,
                    'ref': accounting_ref, # ID in accounting                    
                    'anomaly': anomaly,
                    }

                if lot_ids:
                    lot_id = lot_ids[0]
                    self.write(cr, uid, lot_id, data, context=context)    
                else:
                    lot_id = self.create(cr, uid, data, context=context)                    
                lot_modify_ids.append(lot_id)    
            except:            
                _logger.error("Umanaged error: %s" % (sys.exc_info(), ))        
            
        # reset lot not present:
        no_stock_ids = self.search(cr, uid, [('id', 'not in', lot_modify_ids)], context=context)
        self.write(cr, uid, no_stock_ids, {
            'stock_available_accounting': 0.0,
            }, context=context)
        return True
        
    _columns = {
        'package_id': fields.many2one('product.ul', 'Package', 
            help='Package used for package (for this lot)'),
        'stock_available_accounting': fields.float('Stock availability', digits=(16, 2)),    
        #'package_ref': fields.char('Package ref', size=12, 
        #    help="Reference for import package, used to find product (or for "
        #        "save in lot if there's no product"),
        'accounting_ref': fields.char('Accounting ref', size=12, 
            help="ID lot in account program"),
        'anomaly': fields.boolean('Anomaly', required=False),    
    }    

class product_product_lot_accounting(orm.Model):
    ''' Add extra field for manage status of product / lot from accounting
    '''
    _name = 'product.product'
    _inherit = 'product.product'
    
    _columns = {
        'accounting_lot_ids': fields.one2many('stock.production.lot', 
            'product_id', 'Lots status'),
        'package_ref': fields.char('Package ref', size=12, 
            help="Reference for import package, used to find product"),    
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
