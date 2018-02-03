from secret import *

CERT = '/usr/local/etc/nginx/cert.pem'
WEBHOOK_HOST = 'webhooks.bakunin.nl/mud'
REDIS = {'host': 'localhost', 'port': 6379}

from os import getenv, uname
if getenv('IS_PLAYGROUND') or uname()[0] == "Darwin":
    IS_PLAYGROUND = True
    import settings_playground
else:
    IS_PLAYGROUND = False
