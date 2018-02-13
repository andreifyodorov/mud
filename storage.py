from itertools import chain
from redis import StrictRedis
import pprint

from mud.states import State, PlayerState, World
from mud.npcs import NpcState
from mud.locations import Location
from mud.production import MeansOfProduction, Land
from mud.commodities import Commodity, Vegetable

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
        self.version = int(self.redis.get('version') or 0)
        self.world = World()

        serialized_world = redis.get('world')
        if serialized_world:
            self.deserialize_state(self.world, eval(serialized_world))

        for location_id in Location.all.iterkeys():
            serialized = redis.get(LOCATION_KEY % location_id)
            if serialized is not None:
                self.deserialize_state(self.world[location_id], eval(serialized))


    def get_player_state(self, chatkey):
        if chatkey in self.players:
            return self.players[chatkey]

        player = PlayerState(send_callback=self.send_callback_factory(chatkey))

        serialized = self.redis.get(PLAYER_KEY % chatkey)
        if serialized is not None:
            self.deserialize_state(player, eval(serialized))

        self.chatkeys[player] = chatkey
        self.players[chatkey] = player
        return player


    def dump(self):
        for chatkey, state in self.players.iteritems():
            yield "player:%s" % chatkey, self.serialize_state(state)
        for location_id, state in self.world.iteritems():
            yield "location:%s" % location_id, self.serialize_state(state)
        yield "world", self.serialize_state(self.world)
        yield "version", self.version


    def save(self):
        for k, v in self.dump():
            self.redis.set(k, repr(v))
        self.lock_object.release()


    def print_dump(self):
        for k, v in self.dump():
            print "%s\t%s" % (k, pprint.pformat(v))


    def deserialize_state(self, state, data):
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
                    c.__subclasses__() for c in (NpcState, Commodity, MeansOfProduction))
                for subcls in subclasses:
                    if subcls.__name__ == cls:
                        o = subcls()
                        break
                if isinstance(arg, dict):
                    self.deserialize_state(o, arg)
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
            if v is not None and v is not False:
                serialized[k] = v
        return serialized


    def serialize(self, o):
        if isinstance(o, Location):
            return ('Location', o.id)
        elif isinstance(o, PlayerState):
            return ('PlayerState', self.chatkeys[o])
        elif isinstance(o, NpcState):
            return (o.__class__.__name__, self.serialize_state(o))
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


    def all_npcs(self):
        return self.world.all_npcs()
