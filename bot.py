from collections import defaultdict

from mud.chatflow import CommandPrefix
import settings

import telegram


class Bot(telegram.Bot):
    cmd_pfx = CommandPrefix('/')

    def __init__(self, *args, **kwargs):
        super(Bot, self).__init__(settings.TOKEN, *args, **kwargs)
        self.message_queue = defaultdict(list)

    def send_callback_factory(self, chatkey):
        def callback(msg):
            self.message_queue[chatkey].append(msg)
        return callback

    def send_messages(self):
        while self.message_queue:
            chat_id, messages = self.message_queue.popitem()
            text = "\n\n".join(messages)
            self.sendMessage(parse_mode="Markdown", chat_id=chat_id, text=text)


bot = Bot()
