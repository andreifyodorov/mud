# coding: utf8
from .states import ActorState, PlayerState, NpcMixin
from .mutators import StateMutator, ExitGuardMixin
from .commodities import Edibles, DirtyRags, Overcoat, FlamboyantAttire, RoughspunTunic, Spindle
from .locations import Field, Village, VillageHouse, TownGate, MarketSquare


class IsNotDoneYet(Exception):
    pass


class NpcMutator(StateMutator):
    def set_counter(self, counter, value):
        self.actor.counters[counter] = value

    def dec_counter(self, counter):
        value = self.actor.counters.get(counter, None)
        if value is not None and value > 0:
            self.actor.counters[counter] = value - 1
        else:
            if value is not None:
                del self.actor.counters[counter]
            return True

    def is_done(self, doing, doing_descr, done_in):
        if doing not in self.actor.counters:
            self.set_counter(doing, done_in)

        if self.actor.doing_descr != doing_descr:
            self.anounce("is %s." % doing_descr)
            self.actor.doing_descr = doing_descr

        elif self.dec_counter(doing):
            if self.actor.doing_descr == doing_descr:
                self.actor.doing_descr = None
            return True

        raise IsNotDoneYet()


    def act(self):
        if ('resting' not in self.actor.counters
                and not self.actor.tired
                and self.dec_counter('tired')):
            self.actor.tired = True

        if ('eating' not in self.actor.counters
                and not self.actor.hungry
                and self.dec_counter('hungry')):
            self.actor.hungry = True

        try:
            self.ai()
        except IsNotDoneYet:
            pass


class NpcState(ActorState, NpcMixin):
    mutator_class = None

    def __init__(self, name=None):
        super(NpcState, self).__init__(name)

        self.counters = {}
        self.doing_descr = None
        self.hungry = False
        self.tired = False
        self.accumulate = False


    @property
    def descr(self):
        descr = super(NpcState, self).descr
        if self.doing_descr:
            descr = '%s %s' % (descr, self.doing_descr)
        return descr

    def get_mutator(self, world):
        if self.mutator_class is None:
            return None
        return self.mutator_class(self, world)


class PeasantMutator(NpcMutator):
    default_wear = RoughspunTunic

    def ai(self):
        edibles = (i for i in self.location.items if isinstance(i, Edibles))
        if self.pick(edibles):
            return  # end cycle

        if self.actor.hungry:
            edible = next(self.actor.bag.filter(Edibles), None)
            if edible and self.is_done("eating", "eating %s" % edible.name, 10):
                self.eat(edible)
                self.actor.hungry = False
                self.set_counter("hungry", 100)

        if self.actor.tired:
            if self.actor.location is Field:
                if self.is_done("walking", "tired and going home", 5):
                    self.go('north')

            if self.actor.location is Village:
                if self.is_done("walking", "tired and going home", 5):
                    self.go('enter')

            if self.actor.location is VillageHouse:
                if self.is_done("resting", "resting", 20):
                    self.actor.tired = False
                    self.set_counter("tired", 100)

        if (self.actor.location is VillageHouse
                and not next(self.actor.bag.filter(Spindle), None)):
            if self.is_done("crafting", "making a spindle", 10):
                spindle = Spindle()
                self.actor.bag.add(spindle)
                self.anounce("makes %s." % spindle.name)

        count_edibles = len(list(self.actor.bag.filter(Edibles)))
        if not self.actor.accumulate and count_edibles <= 1:
            self.actor.accumulate = True
        elif self.actor.accumulate and count_edibles >= 5:
            self.actor.accumulate = False

        if self.actor.accumulate:
            if self.actor.location is VillageHouse:
                if self.is_done("walking", "going to a field", 5):
                    self.go('exit')

            if self.actor.location is Village:
                if self.is_done("walking", "going to a field", 5):
                    self.go('south')

            if self.actor.location is Field:
                if self.is_done("farming", "farming", 20):
                    field, = self.location.means
                    self.produce(field)


class PeasantState(NpcState):
    mutator_class = PeasantMutator
    abstract_name = "a peasant"
    definite_name = "the peasant"
    icon = u'👵'

    @property
    def barters(self):
        return len(self.bag) > 0


class GuardMutator(StateMutator):
    default_wear = Overcoat

    def act(self):
        pass

    def allow(self, visitor, to):
        if (isinstance(visitor.wears, DirtyRags)
                and self.actor.location is TownGate
                and to is MarketSquare):
            if isinstance(visitor, PlayerState):
                visitor.send("The guard blocks your way and pushes you away.")
                self.say_to(visitor,
                    "We don't allow filthy beggars on our streets! "
                    "Get yourself some proper clothes and then you may pass.")
            return False
        return True


class GuardState(NpcState, ExitGuardMixin):
    mutator_class = GuardMutator
    abstract_name = 'a guard'
    icon = u'👮'


class MerchantMutator(StateMutator):
    default_wear = FlamboyantAttire

    def act(self):
        pass


class MerchantState(NpcState):
    mutator_class = MerchantMutator
    abstract_name = 'a merchant'
    icon = u'🤵'
    buys = True

    @property
    def for_sale(self):
        return self.bag

    @property
    def sells(self):
        return len(self.for_sale) > 0
