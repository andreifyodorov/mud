from .commodities import Commodity, Wearables, Wieldables, Deteriorates
from .utils import pretty_list
from itertools import chain


class ExitGuardState(object):
    pass


class StateMutator(object):
    def __init__(self, actor, world):
        self.actor = actor
        self.world = world

    @property
    def location(self):
        return self.world[self.actor.location.id]

    @property
    def others(self):
        return (a for a in self.location.actors if a is not self.actor)

    def anounce(self, message):
        self.location.broadcast("%s %s" % (self.actor.Name, message), skip_sender=self.actor)

    def say_to(self, actor, message):
        actor.send("*%s*: %s" % (self.actor.Name, message))

    def spawn(self, location):
        if not self.actor.location and not self.actor.alive:
            if self.default_wear:
                self.actor.wears = self.default_wear()
            self.actor.alive = True
            self.actor.location = location
            self.location.actors.add(self.actor)
            self.anounce('materializes.')

    def die(self):
        if self.actor.alive:
            self.anounce('dies.')
            self.location.actors.remove(self.actor)
            self.location.items.update(self.actor.bag)
            self.actor.bag.clear()
            self.actor.location = None
            self.actor.alive = False

    def go(self, direction):
        old = self.actor.location
        new = self.actor.location.exits[direction]['location']

        guards = (a for a in self.location.actors if isinstance(a, ExitGuardState))
        for guard in guards:
            if not guard.get_mutator(self.world).allow(self.actor, new):
                return False

        self.anounce('leaves to %s.' % new.name)
        self.location.actors.remove(self.actor)
        self.actor.location = new
        self.anounce('arrives from %s.' % old.name)
        self.location.actors.add(self.actor)
        self.deteriorate(self.actor.wears)
        return True

    def _relocate(self, item_or_items, source, destination=None, dry=False):
        items = set()
        try:
            items.update(item_or_items)
        except TypeError:
            items.add(item_or_items)
        items = items & source
        if items and not dry:
            if destination is not None:
                destination.update(items)
            source.difference_update(items)
        return items

    def pick(self, item_or_items):
        items = self._relocate(item_or_items, self.location.items, self.actor.bag)
        if items:
            self.anounce('picks up %s.' % pretty_list(items))
        return items

    def drop(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag, self.location.items)
        if items:
            self.anounce('drops %s on the ground.' % pretty_list(items))
        return items

    def eat(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag)
        if items:
            self.anounce('eats %s.' % pretty_list(items))
        return items

    def _relocate_to_slot(self, slot, item):
        current = getattr(self.actor, slot)
        if current is item:
            return False
        items = self._relocate(item, self.actor.bag)
        if not items:
            return False
        item, = items
        setattr(self.actor, slot, item)
        if current is not None:
            self.actor.bag.add(current)
        return True

    def wear(self, item):
        if isinstance(item, Wearables) and self._relocate_to_slot('wears', item):
            self.anounce('wears %s.' % item.name)
            return True
        return False

    def wield(self, item):
        if isinstance(item, Wieldables) and self._relocate_to_slot('wields', item):
            self.anounce('wields %s.' % item.name)
            return True
        return False

    def unequip(self):
        item = self.actor.wields
        if item:
            self.anounce('puts away %s.' % item.name)
            self.actor.wields = None
            self.actor.bag.add(item)
            return item

    def barter(self, counterparty, what, for_what):
        if (counterparty.barters
                and counterparty.get_mutator(self.world).accept_barter(self.actor, what, for_what)):
            self.anounce('barters %s for %s with %s.'
                         % (pretty_list(what), pretty_list(for_what), counterparty.name))
            return True
        return False

    def accept_barter(self, counterparty, what, for_what):
        return (
            self._relocate(what, counterparty.bag, self.actor.bag)
            and self._relocate(for_what, self.actor.bag, counterparty.bag))

    def sell(self, counterparty, what):
        if (counterparty.buys
                and counterparty.get_mutator(self.world).accept_buy(self.actor, what)):
            self.anounce('sells %s to %s.' % (pretty_list(what), counterparty.name))
            return True
        return False

    def accept_sell(self, counterparty, what):
        self._relocate(what, self.actor.bag, counterparty.bag)
        price = 1 if isinstance(what, Commodity) else len(what)
        self.actor.credits += price
        counterparty.credits -= price
        return True

    def buy(self, counterparty, what):
        if (counterparty.sells
                and counterparty.get_mutator(self.world).accept_sell(self.actor, what)):
            self.anounce('buys %s from %s.' % (pretty_list(what), counterparty.name))
            return True
        return False

    def accept_buy(self, counterparty, what):
        self._relocate(what, counterparty.bag, self.actor.bag)
        price = 1 if isinstance(what, Commodity) else len(what)
        self.actor.credits -= price
        counterparty.credits += price
        return True

    def produce_missing(self, means, missing=None):
        if missing is None:
            missing = []
        tools = {}
        # get required/optional tools
        for t in means.optional_tools | means.required_tools:
            tool = None
            if isinstance(self.actor.wields, t):
                tool = self.actor.wields
            else:
                tool = next(self.actor.bag.filter(t), None)
            if tool:
                tools[t] = tool
            elif t in means.required_tools:
                missing.append(t)
        # get required materials
        materials = {}
        for t, n in means.required_materials.items():
            loc = list(self.actor.bag.filter(t))
            if len(loc) >= n:
                materials[t] = loc[:n]
            else:
                missing.extend([t] * (n - len(loc)))
        # do we miss something?
        return missing, tools, materials

    def can_produce(self, means):
        missing, tools, materials = self.produce_missing(means)
        return False if missing else True

    def produce(self, means, missing=None):
        missing, tools, materials = self.produce_missing(means, missing)
        if missing:
            return

        if self.actor.last_success_time and self.actor.last_success_time == self.world.time:
            return

        self._relocate(chain.from_iterable(materials.values()), self.actor.bag)

        fruit_or_fruits = means.produce(tools, materials)
        if fruit_or_fruits is None:
            return
        fruits = [fruit_or_fruits] if isinstance(fruit_or_fruits, Commodity) else fruit_or_fruits

        if tools:
            tool, = tools.values()
            self.wield(tool)
            self.deteriorate(tool)
        else:
            self.unequip()

        self.actor.last_success_time = self.world.time
        self.anounce('%ss %s.' % (means.verb, pretty_list(fruits)))
        self.actor.bag.update(fruits)

        return fruits

    def deteriorate(self, commodity):
        if not isinstance(commodity, Deteriorates):
            return False

        commodity.usages += 1
        if commodity.usages < commodity.max_usages:
            return False

        replace = None
        if hasattr(commodity, 'deteriorates_into'):
            replace = commodity.deteriorates_into()

        if self.actor.wears is commodity:
            self.actor.wears = replace

        elif self.actor.wields is commodity:
            self.actor.wields = replace

        elif commodity in self.actor.bag:
            self._relocate(commodity, self.actor.bag)
            if replace:
                self.actor.bag.add(replace)

        self.location.broadcast(commodity.deteriorate(f"{self.actor.name}'s"), skip_sender=self.actor)

        return True
