# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import erppeek
import ConfigParser
import smtplib
import pdb
from datetime import datetime
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.mime.text import MIMEText
from email import Encoders

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.cfg')
now = ('%s' % datetime.now())[:19]

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# ERP Connection:
odoo = {
    'database': config.get('dbaccess', 'dbname'),
    'user': config.get('dbaccess', 'user'),
    'password': config.get('dbaccess', 'pwd'),
    'server': config.get('dbaccess', 'server'),
    'port': config.get('dbaccess', 'port'),
    }

# Mail:
smtp = {
    'report_mode': config.get('smtp', 'reorder_mode').split(','),
    'text':
        '''<p>Fecha: %s</p>
              <p>Inventario actual de las materias primas y productos terminados y importados.<br/>
                 Checar los producto rojos para organizar la produccion y la las compras. <br/>
                 No estan contemplados os pedidos de clientess y proveedores.
              </p>  
        ''' % now,
    'subject': 'PCA Reordering point status: %s' % now,
    'folder': config.get('smtp', 'folder'),
    }

now = now.replace('/', '_').replace('-', '_').replace(':', '_')

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (odoo['server'], odoo['port']),
    db=odoo['database'],
    user=odoo['user'],
    password=odoo['password'],
    )
mailer = odoo.model('ir.mail_server')
model = odoo.model('ir.model.data')

# -----------------------------------------------------------------------------
# SMTP Sent:
# -----------------------------------------------------------------------------
# Get mailserver option:
mailer_ids = mailer.search([
    ('name', '=', 'PCA')])
if not mailer_ids:
    print('[ERR] No mail server configured in ODOO')
    sys.exit()

odoo_mailer = mailer.browse(mailer_ids)[0]

# Open connection:
print('[INFO] Sending using "%s" connection [%s:%s]' % (
    odoo_mailer.name,
    odoo_mailer.smtp_host,
    odoo_mailer.smtp_port,
    ))

if odoo_mailer.smtp_encryption in ('ssl', 'starttls'):
    smtp_server = smtplib.SMTP_SSL(
        odoo_mailer.smtp_host, odoo_mailer.smtp_port)
else:
    print('[ERR] Connect only SMTP SSL server!')
    sys.exit()

# smtp_server.ehlo()  # open the connection
# smtp_server.starttls()
smtp_server.login(odoo_mailer.smtp_user, odoo_mailer.smtp_pass)

# Extract 2 files
if not smtp['report_mode']:
    print('No recipients present')
    sys.exit()

filename = u'PCA Reordering point stock %s.xlsx' % now
fullname = os.path.expanduser(
    os.path.join(smtp['folder'], filename))
context = {
    'save_mode': fullname,
    }

# Setup context for MRP:
odoo.context = context
company = odoo.model('res.company')

# Launch extract procedure for this mode:
company.extract_product_level_xlsx([])

for to in smtp['report_mode']:
    to = to.replace(' ', '')
    print('Sending mail to %s ...' % to)
    msg = MIMEMultipart()
    msg['Subject'] = smtp['subject']
    msg['From'] = odoo_mailer.smtp_user
    msg['To'] = ','.join(smtp['report_mode'])  # XXX See all delivery!
    msg.attach(MIMEText(smtp['text'], 'html'))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(open(fullname, 'rb').read())
    Encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition', 'attachment; filename="%s"' % filename)

    msg.attach(part)

    # Send mail:
    smtp_server.sendmail(odoo_mailer.smtp_user, to, msg.as_string())
smtp_server.quit()
