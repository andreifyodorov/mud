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
ENTITY_KEY = "entity:%s:%s"


redis = StrictRedis(**settings.REDIS)

if settings.IS_PLAYGROUND:
    redis.delete('global_lock')


class Storage(object):
    entity_classes = (NpcState, Commodity, MeansOfProduction)  # order matters

    def __init__(self, send_callback_factory, redis_=None, chatkey_type=None):
        self.send_callback_factory = send_callback_factory
        self.redis = redis_ or redis
        self.chatkey_type = chatkey_type or int
        self.players = {}
        self.chatkeys = {}

        self.entity_subclasses = [sc for c in self.entity_classes for sc in c.__subclasses__()]
        self.entity_subclass_by_name = {sc.__name__: sc for sc in self.entity_subclasses}
        self.entities = {classname: {} for classname in self.entity_subclass_by_name.iterkeys()}
        self.entitykeys = {}

        self.lock_object = redis.lock('global_lock', timeout=2)
        self.lock_object.acquire()
        self.version = int(self.redis.get('version') or 0)

        world = World()
        serialized_world = redis.get('world')
        if serialized_world:
            self.deserialize_state(world, eval(serialized_world))
        self.world = world

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


    def get_entity_state(self, classname, arg):
        cls = self.entity_subclass_by_name.get(classname, None)
        if cls is None:
            return
        entity = cls()
        key = None
        if isinstance(arg, int):
            key = arg
            self.entities[classname][key] = entity
            serialized = self.redis.get(ENTITY_KEY % (classname, key))
            if serialized is not None:
                self.deserialize_state(entity, eval(serialized))
        else:
            self.deserialize_state(entity, arg)
        self.entitykeys[entity] = key
        return entity


    def dump(self):
        for chatkey, state in self.players.iteritems():
            yield PLAYER_KEY % chatkey, self.serialize_state(state)
        for location_id, state in self.world.iteritems():
            yield LOCATION_KEY % location_id, self.serialize_state(state)
        for cls in self.entity_subclasses:
            classname = cls.__name__
            for key, entity in self.entities[classname].iteritems():
                serialized = self.serialize_state(entity)
                if serialized:
                    yield ENTITY_KEY % (classname, key), serialized
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
                return self.get_entity_state(cls, arg)
        elif isinstance(v, list):
            return [self.deserialize(o) for o in v]
        elif isinstance(v, dict):
            deserialized = {}
            for key, val in v.iteritems():
                deserialized[self.deserialize(key)] = self.deserialize(val)
            return deserialized
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


    def serialize_entity(self, entity):
        classname = entity.__class__.__name__
        key = self.entitykeys.get(entity, None)
        if key is None:
            if self.entities[classname]:
                key = max(0, max(self.entities[classname].iterkeys())) + 1
            else:
                key = 1
            self.entitykeys[entity] = key
            self.entities[classname][key] = entity
        return (classname, key)


    def serialize(self, o):
        if isinstance(o, Location):
            return ('Location', o.id)
        elif isinstance(o, PlayerState):
            return ('PlayerState', self.chatkeys[o])
        elif isinstance(o, self.entity_classes):
            return self.serialize_entity(o)
        elif isinstance(o, (set, list)):
            return [self.serialize(x) for x in o]
        elif isinstance(o, dict):
            serialized = {}
            for k, v in o.iteritems():
                serialized[k] = self.serialize(v)
            return serialized
        elif isinstance(o, (basestring, int, float, bool)):
            return o


    def all_players(self):
        keys = (key.split(":", 1) for key in redis.keys(PLAYER_KEY % "*"))
        for prefix, chatkey in keys:
            yield self.get_player_state(self.chatkey_type(chatkey))


    def all_npcs(self):
        return self.world.all_npcs()
