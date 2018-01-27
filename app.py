#!/usr/bin/env python

from os import getenv
from collections import defaultdict
from itertools import count
from flask import Flask, request
from chatflow import Player, Chatflow
import telegram
import settings

if getenv('IS_PLAYGROUND'):
    import settings_playground


bot = telegram.Bot(settings.TOKEN)
bot.setWebhook(url='https://%s/%s' % (settings.WEBHOOK_HOST, settings.TOKEN),
               certificate=open(settings.CERT, 'rb'))
# print bot.getWebhookInfo()

app = Flask(__name__)
user_context = defaultdict(lambda c=count(): Player(next(c)))

@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    update = telegram.update.Update.de_json(request.get_json(force=True), bot)

    text = update.message.text
    chatkey = update.message.chat_id

    if text is not None:
        chatflow = Chatflow(
            actor=user_context[chatkey],
            world={},
            reply_callback=lambda text: bot.sendMessage(chat_id=chatkey, text=text),
            command_prefix='/')

        chatflow.process_message(text)

    return 'OK'
