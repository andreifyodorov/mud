from os.path import expanduser
import settings

settings.TOKEN = '498422063:AAH1eDOCvmOZdPwrWW75CZOAdeeGuKYgPmY'

LOCAL_BAKUNIN_CONF_PATH = expanduser('~/bakunin/conf')
settings.CERT = LOCAL_BAKUNIN_CONF_PATH + settings.CERT

settings.WEBHOOK_HOST = 'playground.bakunin.nl'
