#!/usr/bin/env python

from os import getenv
from collections import defaultdict
from itertools import count
from flask import Flask, request
import telegram
import redis

from chatflow import State, PlayerState, WorldState, Chatflow
from locations import Location, StartLocation
from commodities import Commodity, Vegetable

import settings

if getenv('IS_PLAYGROUND'):
    import settings_playground


bot = telegram.Bot(settings.TOKEN)
bot.setWebhook(url='https://%s/%s' % (settings.WEBHOOK_HOST, settings.TOKEN),
               certificate=open(settings.CERT, 'rb'))
# print bot.getWebhookInfo()

app = Flask(__name__)
redis = redis.StrictRedis(**settings.REDIS)
redis.delete('global_lock')

class States(object):
    def __init__(self, redis):
        self.redis = redis
        self.players = {}
        self.chatkeys = {}

        self.lock_object = self.redis.lock('global_lock')
        self.lock_object.acquire()

        self.world = {}
        for location_id in Location.all.iterkeys():
            state = WorldState()
            serialized = self.redis.get("location:%s" % location_id)
            if serialized is not None:
                self.deserialize_state(state, serialized)
            self.world[location_id] = state


    def get_player_state(self, chatkey):
        if chatkey in self.players:
            return self.players[chatkey]

        send_callback = lambda text: bot.sendMessage(chat_id=chatkey, text=text)
        player = PlayerState(send_callback=send_callback)

        serialized = self.redis.get("player:%s" % chatkey)
        if serialized is not None:
            self.deserialize_state(player, serialized)

        self.chatkeys[player] = chatkey
        self.players[chatkey] = player
        return player


    def save(self):
        for chatkey, state in self.players.iteritems():
            self.redis.set("player:%s" % chatkey, repr(self.serialize_state(state)))

        for location_id, state in self.world.iteritems():
            self.redis.set("location:%s" % location_id, repr(self.serialize_state(state)))

        self.lock_object.release()


    def deserialize_state(self, state, serialized):
        data = eval(serialized)
        for k, v in data.iteritems():
            o = self.deserialize(v)
            attr = getattr(state, k, None)
            if attr is not None and hasattr(attr, 'update'):
                attr.update(o)
            else:
                setattr(state, k, o)


    def deserialize(self, v):
        if isinstance(v, tuple):
            cls, arg = v
            if cls == 'Location':
                return Location.all[arg]
            elif cls == 'PlayerState':
                return self.get_player_state(arg)
            else:
                o = None
                for subcls in Commodity.__subclasses__():
                    if subcls.__name__ == cls:
                        o = subcls()
                        break
                if isinstance(arg, dict):
                    for k, v in arg:
                        setattr(o, k, v)
                return o
        elif isinstance(v, list):
            return [self.deserialize(o) for o in v]
        else:
            return v


    def serialize_state(self, state):
        serialized = {}
        for k, o in vars(state).iteritems():
            if isinstance(o, (dict, set)) and not o:
                continue
            v = self.serialize(o)
            if v is not None:
                serialized[k] = v
        return serialized


    def serialize(self, o):
        if isinstance(o, Location):
            return ('Location', o.id)
        elif isinstance(o, PlayerState):
            return ('PlayerState', self.chatkeys[o])
        elif isinstance(o, Commodity):
            return (o.__class__.__name__, o.__dict__)
        elif isinstance(o, (set, list)):
            return [self.serialize(x) for x in o]
        elif isinstance(o, (basestring, int, float, bool, dict)):
            return o



@app.route('/' + settings.TOKEN, methods=['POST'])
def webhook():
    update = telegram.update.Update.de_json(request.get_json(force=True), bot)

    text = update.message.text
    chatkey = update.message.chat_id

    if text is not None:
        state = States(redis)
        chatflow = Chatflow(state.get_player_state(chatkey), state.world, command_prefix='/')
        chatflow.process_message(text)
        state.save()

    return 'OK'
