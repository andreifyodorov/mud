from itertools import chain
from redis import StrictRedis

from chatflow import State, PlayerState, WorldState, Chatflow
from locations import Location
from production import MeansOfProduction, Land
from commodities import Commodity, Vegetable

import settings


PLAYER_KEY = "player:%s"
LOCATION_KEY = "location:%s"


redis = StrictRedis(**settings.REDIS)

if settings.IS_PLAYGROUND:
    redis.delete('global_lock')


class Storage(object):
    def __init__(self, send_callback_factory, redis_=None, chatkey_type=None):
        self.send_callback_factory = send_callback_factory
        self.redis = redis_ or redis
        self.chatkey_type = chatkey_type or int
        self.players = {}
        self.chatkeys = {}

        self.lock_object = redis.lock('global_lock', timeout=2)
        self.lock_object.acquire()

        self.world = {}
        for location_id in Location.all.iterkeys():
            state = WorldState()
            serialized = redis.get(LOCATION_KEY % location_id)
            if serialized is not None:
                self.deserialize_state(state, serialized)
            self.world[location_id] = state


    def get_player_state(self, chatkey):
        if chatkey in self.players:
            return self.players[chatkey]

        player = PlayerState(send_callback=self.send_callback_factory(chatkey))

        serialized = self.redis.get(PLAYER_KEY % chatkey)
        if serialized is not None:
            self.deserialize_state(player, serialized)

        self.chatkeys[player] = chatkey
        self.players[chatkey] = player
        return player


    def dump(self):
        for chatkey, state in self.players.iteritems():
            yield "player:%s" % chatkey, repr(self.serialize_state(state))
        for location_id, state in self.world.iteritems():
            yield "location:%s" % location_id, repr(self.serialize_state(state))


    def save(self):
        for k, v in self.dump():
            self.redis.set(k, v)
        self.lock_object.release()


    def print_dump(self):
        for k, v in self.dump():
            print "%s\t%s" % (k, v)


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
                subclasses = chain.from_iterable(
                    c.__subclasses__() for c in (Commodity, MeansOfProduction))
                for subcls in subclasses:
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
        elif isinstance(o, (Commodity, MeansOfProduction)):
            return (o.__class__.__name__, o.__dict__)
        elif isinstance(o, (set, list)):
            return [self.serialize(x) for x in o]
        elif isinstance(o, (basestring, int, float, bool, dict)):
            return o


    def all_players(self):
        keys = (key.split(":", 1) for key in redis.keys(PLAYER_KEY % "*"))
        for prefix, chatkey in keys:
            yield self.get_player_state(self.chatkey_type(chatkey))

    @property
    def version(self):
        return self.redis.get('version')

    @version.setter
    def version(self, value):
        self.redis.set('version', value)

