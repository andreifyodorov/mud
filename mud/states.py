# coding: utf-8

from .locations import Location


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
        return (a for l in self.values() for a in l.actors if isinstance(a, NpcMixin))

    def enact(self):
        self.time = self.time or 0
        for npc in set(self.all_npcs()):
            npc.get_mutator(self).act()
        self.time += 1


class State(object):
    pass


class ActorState(State):
    def __init__(self, name=None):
        super(ActorState, self).__init__()
        if not hasattr(self, 'name'):
            self.name = name
        self.alive = False
        self.location = None
        self.bag = set()
        self.coins = 0
        self.wears = None
        self.last_success_time = 0

    @property
    def Name(self):
        return self.name[0].upper() + self.name[1:]  # works better than capitalize


class PlayerState(ActorState):
    def __init__(self, send_callback):
        super(PlayerState, self).__init__()
        self.send = send_callback or (lambda message: None)
        self.input = {}
        self.chain = {}

    @property
    def descr(self):
        return '%s (player)' % self.name


class WorldState(State):
    def __init__(self):
        super(WorldState, self).__init__()
        self.items = set()
        self.actors = set()
        self.means = set()

    @property
    def npcs(self):
        return (a for a in self.actors if isinstance(a, NpcMixin))

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors:
            if skip_sender is not None and actor is skip_sender:
                continue
            if isinstance(actor, PlayerState):
                actor.send(message.capitalize())
