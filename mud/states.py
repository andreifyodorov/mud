from . import commodities
from .utils import FilterSet


class State(object):
    icon = None
    abstract_name = None

    def __init__(self):
        self.cooldown = {}

    @property
    def name_without_icon(self):
        return self.abstract_name

    def _add_icon(self, name):
        return "%s %s" % (self.icon, name) if self.icon else name

    @property
    def name(self):
        return self._add_icon(self.name_without_icon)

    @property
    def Name(self):
        name = self.name_without_icon
        name = name[0].upper() + name[1:]  # works better than capitalize
        return self._add_icon(name)


class ActorState(State):
    definite_name = None
    _name = None
    abstract_descr = None
    barters = False
    sells = False
    buys = False
    recieves_announces = False
    max_hitpoints = None

    def __init__(self, name=None):
        super(ActorState, self).__init__()
        self.name = name
        self.alive = False
        self.location = None
        self.bag = FilterSet()
        self.credits = 0
        self.wears = None
        self.wields = None
        self.victim = None
        self.hitpoints = None

    @property
    def name_without_icon(self):
        return self._name or super(ActorState, self).name_without_icon

    @State.name.setter
    def name(self, value):
        self._name = value

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

    @property
    def weapon(self):
        return self.wields if self.wields and isinstance(self.wields, commodities.Weapon) else None

    @property
    def is_high(self):
        return 'high' in self.cooldown
