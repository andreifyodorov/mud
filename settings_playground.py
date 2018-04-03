from os.path import expanduser
import settings

settings.TOKEN = settings.PLAYGROUND_TOKEN

LOCAL_BAKUNIN_CONF_PATH = expanduser('~/bakunin/conf')
settings.CERT = LOCAL_BAKUNIN_CONF_PATH + settings.CERT

settings.WEBHOOK_HOST = 'playground.bakunin.nl'
settings.CYCLE_SECONDS = 10
