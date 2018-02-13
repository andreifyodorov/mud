from mud.chatflow import CommandPrefix

import telegram
import settings


class Bot(telegram.Bot):
    cmd_pfx = CommandPrefix('/')

    def __init__(self, *args, **kwargs):
        super(Bot, self).__init__(settings.TOKEN, *args, **kwargs)

    def send_callback_factory(self, chatkey):
        def callback(msg):
            self.sendMessage(chat_id=chatkey, text=msg, parse_mode="Markdown")
        return callback


bot = Bot()
