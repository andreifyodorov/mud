from redis import StrictRedis
import pprint

from mud.player import PlayerState
from mud.world import WorldState
from mud.npcs import NpcState
from mud.locations import Location
from mud.production import MeansOfProduction
from mud.commodities import Commodity

import settings


class Storage(object):
    entity_classes = (NpcState, Commodity, MeansOfProduction)  # order matters (refs)

    _player_key = "player:%s"
    _location_key = "location:%s"
    _entity_key = "entity:%s:%s"

    @property
    def _default_redis_connection(self):
        redis = StrictRedis(**settings.REDIS)
        if settings.IS_PLAYGROUND:
            redis.delete('global_lock')
        setattr(Storage, '_default_redis_connection', redis)
        return redis

    def __init__(self, send_callback_factory, cmd_pfx, redis=None, chatkey_type=None):
        self.send_callback_factory = send_callback_factory
        self.cmd_pfx = cmd_pfx
        self.redis = redis or self._default_redis_connection
        self.chatkey_type = chatkey_type or int
        self.players = {}
        self.chatkeys = {}

        self.entity_subclasses = [sc for c in self.entity_classes for sc in c.__subclasses__()]
        self.entity_subclass_by_name = {sc.__name__: sc for sc in self.entity_subclasses}
        self.entities = {classname: {} for classname in self.entity_subclass_by_name.keys()}
        self.entitykeys = {}

        self.lock_object = self.redis.lock('global_lock', timeout=2)
        self.lock_object.acquire()
        self.version = int(self.redis.get('version') or 0)

        world = WorldState()
        serialized_world = self.redis.get('world')
        if serialized_world:
            self.deserialize_state(world, eval(serialized_world))
        self.world = world

        for location_id in Location.all.keys():
            serialized = self.redis.get(self._location_key % location_id)
            if serialized is not None:
                self.deserialize_state(self.world[location_id], eval(serialized))

    def get_player_state(self, chatkey):
        if chatkey in self.players:
            return self.players[chatkey]

        player = PlayerState(send_callback=self.send_callback_factory(chatkey), cmd_pfx=self.cmd_pfx)

        serialized = self.redis.get(self._player_key % chatkey)
        if serialized is not None:
            self.deserialize_state(player, eval(serialized))

        self.chatkeys[player] = chatkey
        self.players[chatkey] = player
        return player

    def get_entity_state(self, classname, arg):
        cls = self.entity_subclass_by_name.get(classname, None)
        if cls is None:
            return

        key = None
        if isinstance(arg, int):
            key = arg
            if key in self.entities[classname]:
                return self.entities[classname][key]

        entity = cls()
        if key:
            self.entities[classname][key] = entity
            self.entitykeys[entity] = key
            serialized = self.redis.get(self._entity_key % (classname, key))
            if serialized is not None:
                self.deserialize_state(entity, eval(serialized))
        else:
            self.deserialize_state(entity, arg)
        return entity

    def dump(self):
        for chatkey, state in self.players.items():
            yield self._player_key % chatkey, self.serialize_state(state)
        for location_id, state in self.world.items():
            yield self._location_key % location_id, self.serialize_state(state)
        for cls in self.entity_subclasses:
            classname = cls.__name__
            for key, entity in self.entities[classname].items():
                serialized = self.serialize_state(entity)
                yield self._entity_key % (classname, key), serialized

        yield "world", self.serialize_state(self.world)
        yield "version", self.version

    def save(self):
        for k, v in self.dump():
            if v:
                self.redis.set(k, repr(v))
            else:
                self.redis.delete(k)
        self.lock_object.release()

    def print_dump(self):
        for k, v in self.dump():
            if v:
                print(k, pprint.pformat(v), sep="\t")

    def deserialize_state(self, state, data):
        for k, v in data.items():
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
            for key, val in v.items():
                deserialized[self.deserialize(key)] = self.deserialize(val)
            return deserialized
        else:
            return v

    def serialize_state(self, state):
        serialized = {}
        for k, o in vars(state).items():
            if k == "cmd_pfx":
                continue
            if isinstance(o, (dict, set)) and not o:
                continue
            v = self.serialize(o)
            if k.startswith('_') and isinstance(getattr(type(state), k[1:]), property):
                k = k[1:]
            if v is not None and v is not False and v != 0:
                serialized[k] = v
        return serialized

    def serialize_entity(self, entity):
        classname = entity.__class__.__name__
        key = self.entitykeys.get(entity, None)
        if key is None:
            if self.entities[classname]:
                key = max(0, max(self.entities[classname].keys())) + 1
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
        elif isinstance(o, list):
            return [self.serialize(x) for x in o]
        elif isinstance(o, set):
            return sorted(self.serialize(list(o)))
        elif isinstance(o, dict):
            serialized = {}
            for k, v in o.items():
                serialized[k] = self.serialize(v)
            return serialized
        elif isinstance(o, (str, int, float, bool)):
            return o

    def all_players(self):
        keys = (key.split(b':', 1) for key in self.redis.keys(self._player_key % "*"))
        for prefix, chatkey in keys:
            yield self.get_player_state(self.chatkey_type(chatkey))
