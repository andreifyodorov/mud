from secret import *   # noqa: F401,F403
from os import getenv, uname

CERT = '/usr/local/etc/nginx/cert.pem'
WEBHOOK_HOST = 'webhooks.bakunin.nl/mud'
REDIS = {'host': 'localhost', 'port': 6379}

if getenv('IS_PLAYGROUND') or uname()[0] == "Darwin":
    IS_PLAYGROUND = True
    import settings_playground   # noqa: F401,F402
else:
    IS_PLAYGROUND = False
