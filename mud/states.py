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


# def default_field_mixin_factory(field):
#     _field = "_%s" % field
#     default_field = "default_%s" % field
#     getter = "get_%s" % field
#     setter = "set_%s" % field
#     return type(
#         "Default%sMixin" % field.capitalize(), (object,), {
#             _field: None,
#             default_field: None,
#             getter: lambda self: getattr(self, _field) or getattr(self, default_field),
#             setter: lambda self, value: setattr(self, _field, value),
#             field: property(fget=lambda self: getattr(self, getter)(),
#                             fset=lambda self, value: getattr(self, setter)(value))
#         }
#     )
#

class ActorState(State):
    icon = None
    abstract_name = None
    definite_name = None
    _name = None

    def __init__(self, name=None, icon=None):
        super(ActorState, self).__init__()
        self.name = name
        self.icon = self.icon or icon
        self.alive = False
        self.location = None
        self.bag = set()
        self.diamonds = 0
        self.wears = None
        self.last_success_time = 0

    @property
    def name(self):
        name = self._name or self.abstract_name
        icon = self.icon
        return "%s %s" % (icon, name) if icon else name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def Name(self):
        name = self._name or self.abstract_name
        name = name[0].upper() + name[1:]  # works better than capitalize
        icon = self.icon
        return "%s %s" % (icon, name) if icon else name

    @property
    def descr(self):
        if self._name:
            descr = self._name
            if self.definite_name:
                descr = "%s %s" % (self.name, self.definite_name)
            return descr
        elif self.abstract_descr:
            return self.abstract_descr
        else:
            return self.abstract_name

    @property
    def barters(self):
        return len(self.bag) > 0


class PlayerState(ActorState):
    definite_name = '(player)'

    def __init__(self, send_callback):
        super(PlayerState, self).__init__()
        self.send = send_callback or (lambda message: None)
        self.input = {}
        self.chain = {}


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
                actor.send(message)
