from .states import ActorState, PlayerState, NpcMixin
from .mutators import StateMutator, ExitGuardMixin
from .commodities import Vegetable, DirtyRags, RoughspunTunic, Spindle
from .locations import TownGate, MarketSquare


class NpcState(ActorState, NpcMixin):
    mutator_class = None
    barters = False


    def __init__(self, name=None):
        super(NpcState, self).__init__(name)


    def get_mutator(self, world):
        if self.mutator_class is None:
            return None
        return self.mutator_class(self, world)


class PeasantMutator(StateMutator):
    def spawn(self, location):
        super(PeasantMutator, self).spawn(location)
        self.actor.wears = RoughspunTunic()

    def act(self):
        edibles = (item for item in self.location.items if isinstance(item, Vegetable))
        if self.pick(edibles):
            return  # end cycle

        edibles = (item for item in self.actor.bag if isinstance(item, Vegetable))
        self.eat(edibles)


class PeasantState(NpcState):
    mutator_class = PeasantMutator
    name = 'a peasant'
    descr = 'a hungry and lazy peasant'

    @property
    def barters(self):
        return len(self.bag) > 0


class GuardMutator(StateMutator):
    def act(self):
        pass

    def allow(self, visitor, to):
        if (isinstance(visitor.wears, DirtyRags)
                and self.actor.location is TownGate
                and to is MarketSquare):
            if isinstance(visitor, PlayerState):
                visitor.send("The guard blocks your way and pushes you away.")
                self.say_to(visitor,
                    "We don't allow filthy beggars on ours streets! "
                    "Get yourself some proper clothes and then you may pass.")
            return False
        return True


class GuardState(NpcState, ExitGuardMixin):
    mutator_class = GuardMutator
    name = 'a guard'
    descr = 'a town gate guard'


