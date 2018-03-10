# coding: utf-8
from .locations import Location
from .commodities import DirtyRags
from .utils import FilterSet


class NpcMixin(object):
    pass


class World(dict):
    def __init__(self):
        self.time = 0

    def __getitem__(self, key):
        value = self.get(key, None)
        if value is None:
            if key not in Location.all.keys():
                raise KeyError
            value = self[key] = WorldState()
        return value

    def all_npcs(self):
        return (a for l in self.values() for a in l.actors.filter(NpcMixin))

    def enact(self):
        self.time = self.time or 0
        npcs = set(self.all_npcs())  # npc can change location
        for npc in npcs:
            npc.get_mutator(self).act()
        self.time += 1


class State(object):
    pass


class ActorState(State):
    icon = None
    abstract_name = None
    definite_name = None
    _name = None
    abstract_descr = None
    default_wear = None
    barters = False
    sells = False
    buys = False

    def __init__(self, name=None):
        super(ActorState, self).__init__()
        self.name = name
        self.alive = False
        self.location = None
        self.bag = FilterSet()
        self.credits = 0
        self.wears = None
        self.last_success_time = None

    def _add_icon(self, name):
        return "%s %s" % (self.icon, name) if self.icon else name

    @property
    def name_without_icon(self):
        return self._name or self.abstract_name

    @property
    def name(self):
        return self._add_icon(self.name_without_icon)

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def Name(self):
        name = self.name_without_icon
        name = name[0].upper() + name[1:]  # works better than capitalize
        return self._add_icon(name)

    @property
    def descr(self):
        if self._name:
            descr = self.name
            if self.definite_name:
                descr = "%s %s" % (descr, self.definite_name)
            return descr
        elif self.abstract_descr:
            return self.abstract_descr
        else:
            return self.name


class PlayerState(ActorState):
    definite_name = '(player)'
    default_wear = DirtyRags

    def __init__(self, send_callback):
        super(PlayerState, self).__init__()
        self.send = send_callback or (lambda message: None)
        self.input = {}
        self.chain = {}


class WorldState(State):
    def __init__(self):
        super(WorldState, self).__init__()
        self.items = FilterSet()
        self.actors = FilterSet()
        self.means = FilterSet()

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors:
            if skip_sender is not None and actor is skip_sender:
                continue
            if isinstance(actor, PlayerState):
                actor.send(message)
