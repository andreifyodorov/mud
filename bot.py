import telegram
import settings


class Bot(telegram.Bot):
    command_prefix = '/'

    def __init__(self, *args, **kwargs):
        super(Bot, self).__init__(settings.TOKEN, *args, **kwargs)

    def send_callback_factory(self, chatkey):
        def callback(msg):
            self.sendMessage(chat_id=chatkey, text=msg)
        return callback


bot = Bot()
