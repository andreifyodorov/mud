from .states import ActorState
from .mutators import ActorMutator
from .commodities import Edibles, DirtyRags, Overcoat, FlamboyantAttire, RoughspunTunic, Spindle
from .locations import Field, Village, VillageHouse, TownGate, MarketSquare
from .attacks import HumanAttacks, OrganicAttacks, Bite


class NpcMutator(ActorMutator):
    class IsNotDoneYet(Exception):
        pass

    def set_counter(self, counter, value, announce=None):
        return self._set(self.actor.counters, counter, value, announce)

    def dec_counter(self, counter, announce=None):
        return self._dec(self.actor.counters, counter, announce)

    def is_(self, doing):
        return doing in self.actor.counters

    def is_done(self, doing, doing_descr, done_in):
        if doing not in self.actor.counters:
            self.set_counter(doing, done_in)

        if self.actor.doing_descr != doing_descr:
            self.announce("is %s." % doing_descr)
            self.actor.doing_descr = doing_descr

        elif self.dec_counter(doing):
            if self.actor.doing_descr == doing_descr:
                self.actor.doing_descr = None
            return True

        raise self.IsNotDoneYet

    def act(self):
        super(NpcMutator, self).act()

        if self.actor.victim:
            for method in self.attack_methods():
                self.kick(method)
            if self.actor.victim:
                return  # end cycle

        try:
            self.ai()
        except self.IsNotDoneYet:
            pass

    def ai(self):
        pass


class NpcState(ActorState):
    mutator_class = None

    def __init__(self, name=None):
        super().__init__(name)
        self.counters = {}
        self.doing_descr = None
        self.accumulate = False

    def get_doing_descr(self, perspective=None):
        super_doing_descr = super().get_doing_descr(perspective)
        return super_doing_descr if super_doing_descr else self.doing_descr

    def get_mutator(self, world):
        if self.mutator_class is None:
            return None
        return self.mutator_class(self, world)


class HumanNpcState(NpcState):
    pass


class PeasantMutator(NpcMutator, HumanAttacks):
    default_wear = RoughspunTunic

    def ai(self):
        if self.pick(self.location.items.filter(Edibles)):
            return  # end cycle

        if not self.coolsdown('hungry'):
            edible = next(self.actor.bag.filter(Edibles), None)
            if edible and self.is_done("eating", "eating %s" % edible.name, 10):
                self.eat(edible)
                self.set_cooldown("hungry", 100)

        if not self.coolsdown('tired'):
            if (self.actor.location is Field
                    and self.is_done("walking", "tired and going home", 5)):
                self.go('north')

            if (self.actor.location is Village
                    and self.is_done("walking", "tired and going home", 5)):
                self.go('enter')

            if (self.actor.location is VillageHouse
                    and self.is_done("resting", "resting", 20)):
                self.set_cooldown("tired", 100)

        if (self.actor.location is VillageHouse
                and not any(self.actor.bag.filter(Spindle))
                and self.is_done("crafting", "making a spindle", 10)):
            spindle = Spindle()
            self.actor.bag.add(spindle)
            self.announce("makes %s." % spindle.name)

        if isinstance(self.actor.wears, DirtyRags) and not self.is_("walking"):
            tunic = next(self.actor.bag.filter(RoughspunTunic), None)
            if tunic:
                self.wear(tunic)
            elif self.actor.location is VillageHouse:
                if (self.spin.is_possible
                        and self.is_done("crafting", "spining a yarn", 20)):
                    self.spin()
                    self.unequip()

        count_edibles = len(list(self.actor.bag.filter(Edibles)))
        if not self.actor.accumulate and count_edibles <= 1:
            self.actor.accumulate = True
        elif self.actor.accumulate and count_edibles >= 5:
            self.actor.accumulate = False

        if self.actor.accumulate:
            if (self.actor.location is VillageHouse
                    and self.is_done("walking", "going to a field", 5)):
                self.go('exit')

            if (self.actor.location is Village
                    and self.is_done("walking", "going to a field", 5)):
                self.go('south')

            if (self.actor.location is Field
                    and self.is_done("farming", "farming", 20)):
                self.farm()


class PeasantState(HumanNpcState):
    mutator_class = PeasantMutator
    abstract_name = "a peasant"
    definite_name = "the peasant"  # "Jack the peasant"
    icon = '👵'

    @property
    def barters(self):
        return len(self.bag) > 0


"""
- I can give you a spindle if you give me something in exchange.
- Sometimes you can find cotton in the fields.
- The woods are not too bushy but you can get lost deeper in the forest.
- There are mushrooms in the forest.
- ...
"""


class GuardMutator(NpcMutator, HumanAttacks):
    default_wear = Overcoat

    def allow(self, visitor, to):
        if (isinstance(visitor.wears, DirtyRags)
                and self.actor.location is TownGate
                and to is MarketSquare):
            visitor.send("The guard blocks your way and pushes you away.")
            self.say_to(visitor,
                        "We don't allow filthy beggars on our streets! "
                        "Get yourself some proper clothes and then you may pass.")
            return False
        return True


class GuardState(HumanNpcState):
    mutator_class = GuardMutator
    abstract_name = 'a guard'
    icon = '👮'


class MerchantMutator(NpcMutator, HumanAttacks):
    default_wear = FlamboyantAttire


class MerchantState(HumanNpcState):
    mutator_class = MerchantMutator
    abstract_name = 'a merchant'
    icon = '🤵'
    buys = True

    @property
    def for_sale(self):
        return self.bag

    @property
    def sells(self):
        return len(self.for_sale) > 0


class RatMutator(NpcMutator, OrganicAttacks):
    organic_attacks = {Bite}

    def ai(self):
        if (self.actor.location is not Field):
            direction = next(d for d, e in self.actor.location.exits.items() if e["location"] is Field)
            if self.is_done("walking", "going to a field", 5):
                self.go(direction)


class RatState(NpcState):
    mutator_class = RatMutator
    abstract_name = 'a rat'
    icon = '🐀'
    max_hitpoints = 2
