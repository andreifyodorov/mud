from .states import ActorState, PlayerState, NpcMixin
from .mutators import StateMutator, ExitGuardMixin
from .commodities import Vegetable
from .locations import TownGate, MarketSquare


class NpcState(ActorState, NpcMixin):
    mutator_class = None

    def get_mutator(self, world):
        if self.mutator_class is None:
            return None
        return self.mutator_class(self, world)


class PeasantMutator(StateMutator):
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


class GuardMutator(StateMutator):
    def act(self):
        pass

    def allow(self, actor, to):
        if self.actor.location is TownGate and to is MarketSquare:
            if isinstance(actor, PlayerState):
                actor.send(
                    "The guard blocks your way and pushes you away.\n"
                    "*Guard*: We don't allow nude lunatics on ours streets! "
                    "Get yourself some clothes and then you may pass.")
            return False
        return True


class GuardState(NpcState, ExitGuardMixin):
    mutator_class = GuardMutator
    name = 'a guard'
    descr = 'a town gate guard'


