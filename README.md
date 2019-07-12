# reconcile-config-parse

This script will remove interface configuration from a reconcile configlet and move it to specified static configlets.  Currently it is very specific but could be adjusted to be more general with configlet naming, etc.

python reconcile_configlet_parse.py --cvp=<CVP Name or IP> --user=<CVP User> --passw=<CVP Password> --device=<Network Device to run against>
  
Ex...

python reconcile_configlet_parse.py --cvp=10.10.10.10 --user=cvpadmin --passw=pass123! --device=myswitch.test.com
