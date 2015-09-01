#!/bin/bash
# Parameter to change:
user="administrator@micronaet.local"
password="pwd" 
gid="openerp"
uid="openerp"
server="server"
share="production"
mount_point="/home/administrator/mexal/production"

sudo mount -t cifs //$server/$share $mount_point -o user=$user,password=$password,gid=$gid,uid=$uid

