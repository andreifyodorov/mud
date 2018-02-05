#!/usr/bin/env python

from flask import Flask, request

from bot import telegram, bot
from chatflow import Chatflow
from storage import Storage

import settings


bot.setWebhook(url='https://%s/%s' % (settings.WEBHOOK_HOST, settings.TOKEN),
               certificate=open(settings.CERT, 'rb'))
# print bot.getWebhookInfo()

app = Flask(__name__)


@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    update = telegram.update.Update.de_json(request.get_json(force=True), bot)

    message = update.message.text
    chatkey = update.message.chat_id

    if message is not None:
        storage = Storage(bot.send_callback_factory)
        chatflow = Chatflow(storage.get_player_state(chatkey), storage.world, bot.command_prefix)
        chatflow.process_message(message)
        storage.save()

    return 'OK'


def npcs_acts():
    storage = Storage(bot.send_callback_factory)
    npcs = storage.all_npcs
    for npc in set(npcs):
        npc.mutator_class(npc, storage.world).act()
    storage.save()


try:
    import uwsgi
except:
    pass
else:
    uwsgi.register_signal(30, "worker", npcs_acts)
    uwsgi.add_timer(30, 5)