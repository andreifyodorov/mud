#!/usr/bin/env python

from os import getenv
from collections import defaultdict
from itertools import count
from flask import Flask, request
import telegram

from chatflow import PlayerState, WorldState, Chatflow
from locations import StartLocation
from commodities import Vegetable

import settings

if getenv('IS_PLAYGROUND'):
    import settings_playground


bot = telegram.Bot(settings.TOKEN)
bot.setWebhook(url='https://%s/%s' % (settings.WEBHOOK_HOST, settings.TOKEN),
               certificate=open(settings.CERT, 'rb'))
# print bot.getWebhookInfo()

app = Flask(__name__)
user_states = defaultdict(lambda c=count(): PlayerState(next(c)))
world_states = defaultdict(WorldState)
world_states[StartLocation.id].items.add(Vegetable())


@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    update = telegram.update.Update.de_json(request.get_json(force=True), bot)

    text = update.message.text
    chatkey = update.message.chat_id

    actor = None
    if chatkey in user_states:
        actor = user_states[chatkey]
    else:
        send_callback = lambda text: bot.sendMessage(chat_id=chatkey, text=text)
        actor = user_states[chatkey] = PlayerState(send_callback=send_callback)

    if text is not None:
        chatflow = Chatflow(
            actor=user_states[chatkey],
            world=world_states,
            command_prefix='/')

        chatflow.process_message(text)

    print user_states

    return 'OK'
