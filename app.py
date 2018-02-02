#!/usr/bin/env python

from flask import Flask, request
import telegram

from chatflow import Chatflow
from storage import Storage, redis

import settings
from os import getenv
if getenv('IS_PLAYGROUND'):
    import settings_playground


bot = telegram.Bot(settings.TOKEN)
bot.setWebhook(url='https://%s/%s' % (settings.WEBHOOK_HOST, settings.TOKEN),
               certificate=open(settings.CERT, 'rb'))
# print bot.getWebhookInfo()

app = Flask(__name__)


def send_callback_factory(chatkey):
    def callback(msg):
        bot.sendMessage(chat_id=chatkey, text=msg)
    return callback


@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    update = telegram.update.Update.de_json(request.get_json(force=True), bot)

    message = update.message.text
    chatkey = update.message.chat_id

    if message is not None:
        storage = Storage(redis, send_callback_factory)
        chatflow = Chatflow(storage.get_player_state(chatkey), storage.world, command_prefix='/')
        chatflow.process_message(message)
        storage.save()

    return 'OK'
