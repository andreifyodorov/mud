from mud.chatflow import CommandPrefix

import telegram
import settings


class Bot(telegram.Bot):
    cmd_pfx = CommandPrefix('/')

    def __init__(self, *args, **kwargs):
        super(Bot, self).__init__(settings.TOKEN, *args, **kwargs)
        self.message_queue = []

    def send_callback_factory(self, chatkey):
        def callback(msg):
            self.message_queue.append(dict(chat_id=chatkey, text=msg))
        return callback

    def send_messages(self):
        while self.message_queue:
            message = self.message_queue.pop(0)
            self.sendMessage(parse_mode="Markdown", **message)


bot = Bot()
