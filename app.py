#!/usr/bin/env python

from flask import Flask, request

from bot import telegram, bot
from mud import Chatflow
from storage import Storage

import settings


bot.setWebhook(url='https://%s/%s' % (settings.WEBHOOK_HOST, settings.TOKEN),
               certificate=open(settings.CERT, 'rb'))
# print bot.getWebhookInfo()

app = Flask(__name__)


@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    update = telegram.update.Update.de_json(request.get_json(force=True), bot)

    if update.message is not None:
        message = update.message.text
        chatkey = update.message.chat_id

        storage = Storage(bot.send_callback_factory)
        chatflow = Chatflow(storage.get_player_state(chatkey), storage.world, bot.cmd_pfx)
        chatflow.process_message(message)
        storage.save()

    bot.send_messages()

    return b'OK'


def enact(*args):
    storage = Storage(bot.send_callback_factory)
    storage.world.enact()

    for player in storage.world.all_players():
        if (player.last_command_time is not None
                and storage.world.time - player.last_command_time > 10):
            Chatflow(player, storage.world, bot.cmd_pfx).sleep()

    storage.save()
    bot.send_messages()


try:
    import uwsgi
except:
    pass
else:
    uwsgi.register_signal(30, "worker", enact)
    uwsgi.add_timer(30, 60)