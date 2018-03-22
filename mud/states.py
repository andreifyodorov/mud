from .utils import FilterSet


class State(object):
    icon = None
    abstract_name = None

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

    def __init__(self, name=None):
        super(ActorState, self).__init__()
        self.name = name
        self.counters = {}
        self.alive = False
        self.location = None
        self.bag = FilterSet()
        self.credits = 0
        self.wears = None
        self.wields = None
        self.attacking = None
        self.hit_points = 10
        self.last_success_time = None

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

    def attack(self):
        pass


class PlayerState(ActorState):
    definite_name = '(player)'

    def __init__(self, send_callback):
        super(PlayerState, self).__init__()
        self.send = send_callback or (lambda message: None)
        self.asleep = False
        self.last_command_time = None
        self.last_location = None
        self.input = {}
        self.chain = {}
