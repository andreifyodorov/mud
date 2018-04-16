#!/usr/bin/env python

from flask import Flask, request

from bot import bot
from mud import Chatflow
from storage import Storage

import settings


app = Flask(__name__)


@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    bot_request = bot.get_player_bot_request(request)

    if bot_request:
        storage = Storage(bot_request.send_callback_factory, cmd_pfx=bot.cmd_pfx)
        player = storage.get_player_state(bot_request.chatkey)
        chatflow = Chatflow(player, storage.world, bot.cmd_pfx)
        if bot_request.process_message(chatflow):  # bot-specific UI commands
            storage.release()
        else:
            chatflow.process_message(bot_request.message_text)
            storage.save()
        bot_request.send_messages()

    return b'OK'


def enact(*args):
    bot_request = bot.get_bot_request()
    storage = Storage(bot_request.send_callback_factory, cmd_pfx=bot.cmd_pfx)
    storage.world.enact()
    storage.save()
    bot_request.send_messages()


try:
    import uwsgi
except ImportError:
    pass
else:
    uwsgi.register_signal(30, "worker", enact)
    uwsgi.add_timer(30, settings.CYCLE_SECONDS)
