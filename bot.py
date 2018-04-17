from collections import defaultdict

from mud.player import CommandPrefix
from storage import PlayerSessionsStorage
import settings

import telegram


class BotRequest(object):
    def __init__(self, bot):
        self.bot = bot
        self.message_queue = defaultdict(list)

    def send_callback_factory(self, chatkey):
        def callback(msg):
            self.message_queue[chatkey].append(msg)
        return callback

    def get_send_message_args(self):
        while self.message_queue:
            chatkey, messages = self.message_queue.popitem()
            text = "\n\n".join(messages)
            yield dict(chat_id=chatkey, text=text)

    def send_messages(self):
        for args in self.get_send_message_args():
            self.bot.sendMessage(parse_mode="Markdown", **args)


class PlayerBotRequest(BotRequest):
    category_icons = (
        ('location', '🚶'),
        ('social', '👬'),
        ('inventory', '💼'),
        ('produce', '🛠️'),
        ('general', '…')
    )

    def __init__(self, bot, message, session, cmd_pfx):
        super().__init__(bot)
        self.message = message
        self.session = session
        self.cmd_pfx = cmd_pfx
        self.chatflow = None

    @property
    def message_text(self):
        return self.message.text

    @property
    def chatkey(self):
        return self.message.chat_id

    def get_commands(self):
        return {c: [n for n, f in cmds]
                for c, cmds
                in self.chatflow.get_commands_by_category().items()}

    def process_message(self, chatflow):
        self.chatflow = chatflow
        categories = {i: c for c, i in self.category_icons}
        if self.message.text in categories:
            category = categories[self.message.text]
            self.session.set('category', category)
            return True
        return False

    def get_send_message_args(self):
        commands = self.get_commands()
        category = self.session.get("category")
        if category is None or category not in commands:
            category = next(iter(commands.keys()))
            self.session.set('category', category)

        keyboard = []
        # for category in commands:
        for i in range(0, len(commands[category]), 4):
            row = commands[category][i:i + 4]
            row = [f"{self.cmd_pfx}{c}" for c in row]
            keyboard.append(row)

        icons = {c: i for c, i in self.category_icons}
        icon_row = [icons[c] for c in commands if c in icons]
        if len(icon_row) > 1:
            keyboard.append(icon_row)

        keyboard_repr = repr(keyboard)
        if keyboard_repr == self.session.get('keyboard', 'None'):
            push = False
        else:
            self.session.set('keyboard', keyboard_repr)
            push = True

        reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        flag_seen_player = False
        for args in super().get_send_message_args():
            if args["chat_id"] == self.message.chat_id:
                args.update(reply_markup=reply_markup)
                flag_seen_player = True
            yield args

        if not flag_seen_player and push:
            yield dict(chat_id=self.chatkey, text=f"_Showing {category} commands._", reply_markup=reply_markup)


class Bot():
    cmd_pfx = CommandPrefix('/')

    def __init__(self, *args, **kwargs):
        self.bot = telegram.Bot(settings.TOKEN, *args, **kwargs)
        session_storage = PlayerSessionsStorage()
        self.get_session = session_storage.get_session

    def set_webhook(self, *args, **kwargs):
        self.bot.setWebhook(*args, **kwargs)
        # print self.bot.getWebhookInfo()

    def get_bot_request(self):
        return BotRequest(self.bot)

    def get_player_bot_request(self, request):
        update = telegram.update.Update.de_json(request.get_json(force=True), self)
        if update.message is not None:
            return PlayerBotRequest(self.bot, update.message, self.get_session(update.message.chat_id), self.cmd_pfx)


bot = Bot()
