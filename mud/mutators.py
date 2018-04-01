from .commodities import Commodity, Wearables, Wieldables, Deteriorates, Mushroom
from .utils import credits, pretty_list, FilterSet
from itertools import chain


class StateMutator(object):
    def __init__(self, actor):
        self.actor = actor

    def anounce(self, message, reflect=None):
        raise NotImplemented

    def _set(self, counters, counter, value, anounce=None):
        if value > 0:
            counters[counter] = value - 1
            if anounce:
                self.anounce(f"is {anounce}.", f"are {anounce}.")
            return True
        return False

    def _dec(self, counters, counter, anounce=None):
        value = counters.get(counter, None)
        if value is not None and value > 0:
            counters[counter] = value - 1
            return False
        else:
            if value is not None:
                del counters[counter]
                if anounce:
                    self.anounce(f"is {anounce}.", f"are {anounce}.")
            return True

    def set_cooldown(self, counter, value, anounce=None):
        return self._set(self.actor.cooldown, counter, value, anounce)

    def dec_cooldowns(self):
        for counter in set(self.actor.cooldown):
            self._dec(self.actor.cooldown, counter)

    def coolsdown(self, counter):
        return counter in self.actor.cooldown

    def act(self):
        self.dec_cooldowns()


class ActorMutator(StateMutator):
    default_wear = None

    def __init__(self, actor, world):
        super(ActorMutator, self).__init__(actor)
        self.world = world

    @property
    def location(self):
        return self.world[self.actor.location.id]

    @property
    def others(self):
        return (a for a in self.location.actors if a is not self.actor)

    def set_counter(self, counter, value, anounce=None):
        return self._set(self.actor.counters, counter, value, anounce)

    def dec_counter(self, counter, anounce=None):
        return self._dec(self.actor.counters, counter, anounce)

    def is_(self, doing):
        return doing in self.actor.counters

    def anounce(self, message, reflect=None):
        self.location.broadcast(f"{self.actor.Name} {message}", skip_sender=self.actor)
        if reflect:
            self.actor.send(f"You {reflect}")

    def say_to(self, actor, message):
        actor.send("*%s*: %s" % (self.actor.Name, message))

    def spawn(self, location):
        if not self.actor.location and not self.actor.alive:
            if self.default_wear:
                self.actor.wears = self.default_wear()
            self.actor.alive = True
            self.actor.hitpoints = self.actor.max_hitpoints
            self.victim = None
            self.actor.location = location
            self.location.actors.add(self.actor)
            self.anounce('materializes.')

    def die(self):
        if self.actor.alive:
            self.anounce('dies.', 'die.')
            self._relocate_to_slot('wields', None)
            self._relocate_to_slot('wears', None)
            self.drop(self.actor.bag)
            self.location.actors.remove(self.actor)
            self.actor.location = None
            self.cleanup_victims()
            self.actor.alive = False

    def go(self, direction):
        old = self.actor.location
        new = self.actor.location.exits[direction]['location']

        for actor in self.location.actors:
            if (hasattr(actor.mutator_class, 'allow')
                    and not actor.get_mutator(self.world).allow(self.actor, new)):
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
        return FilterSet(items)

    def pick(self, item_or_items, anounce=None):
        items = self._relocate(item_or_items, self.location.items, self.actor.bag)
        if items:
            items_str = pretty_list(items)
            self.anounce(f'picks up {items_str}.', anounce and anounce(items_str))
        return items

    def drop(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag, self.location.items)
        if items:
            items_str = pretty_list(items)
            self.anounce(f'drops {items_str} on the ground.', f'drop {items_str} on the ground.')
        return items

    def eat(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag)
        if items:
            items_str = pretty_list(items)
            self.anounce(f'eats {items_str}.', f'eat {items_str}.')
        if any(items.filter(Mushroom)):
            self.set_counter('high', 5, anounce='high')
        return items

    def _relocate_to_slot(self, slot, item):
        current = getattr(self.actor, slot)
        if current is item:
            return False
        if item:  # can be None
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
            self.anounce(f'wears {item.name}.', f'wear {item.name}.')
            return item

    def wield(self, item):
        if isinstance(item, Wieldables) and self._relocate_to_slot('wields', item):
            self.anounce(f'wields {item.name}.', f'wield {item.name}.')
            return item

    def unequip(self, anounce=None):
        item = self.actor.wields
        if item:
            self.anounce(f'puts away {item.name}.', anounce and anounce(item))
            self._relocate_to_slot('wields', None)
            return item

    def barter(self, counterparty, what, for_what):
        if (counterparty.barters
                and counterparty.get_mutator(self.world).accept_barter(self.actor, what, for_what)):
            anounce = f"{pretty_list(what)} for {pretty_list(for_what)} with {counterparty.name}"
            self.anounce(f'barters {anounce}.', f'barter {anounce}.')

    def accept_barter(self, counterparty, what, for_what):
        return (
            self._relocate(what, counterparty.bag, self.actor.bag)
            and self._relocate(for_what, self.actor.bag, counterparty.bag))

    def _make_transaction(self, verb, prep, counterparty, what, price, source, destination):
        if self._relocate(what, source, destination):
            self.actor.credits -= price
            counterparty.credits += price
            anounce = f"{pretty_list(what)} {prep} {counterparty.name}"
            self.anounce(f'{verb}s {anounce}.', f'{verb} {anounce} for {credits(abs(price))}.')

    def buy(self, counterparty, what):
        if counterparty.sells:
            price = counterparty.get_mutator(self.world).accept_buy(self.actor, what)
            if price:
                self._make_transaction("buy", "from", counterparty, what, price, counterparty.bag, self.actor.bag)

    def sell(self, counterparty, what):
        if counterparty.buys:
            price = counterparty.get_mutator(self.world).accept_sell(self.actor, what)
            if price:
                self._make_transaction("sell", "to", counterparty, what, -price, self.actor.bag, counterparty.bag)

    def _get_price(self, counterparty, what):
        return 1 if isinstance(what, Commodity) else len(what)

    accept_buy = _get_price
    accept_sell = _get_price

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

        if self.coolsdown('produce'):
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

        self.set_cooldown('produce', 1)
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

    def attack(self, victim, anounce=None):
        self.actor.victim = victim
        if victim.victim is None:
            victim.victim = self.actor
        self.anounce(f'attacks {victim.name}.', anounce)

    def cleanup_victims(self):
        victim = self.actor.victim
        if victim and (not victim.alive or not self.actor.alive):
            if victim.victim is self:
                victim.victim = None
            self.actor.victim = None
            return True

    def kick(self, method):
        victim = self.actor.victim
        if not victim:
            return False

        if self.cleanup_victims():
            return True

        if self.coolsdown(method):
            return False

        if victim.max_hitpoints:
            victim.hitpoints -= method.damage

        if self.actor.is_weapon_method(method):
            self.anounce(f'{method.verb_s} {victim.name} with {self.actor.weapon.name}.',
                         f'{method} {victim.name} with {self.actor.weapon.name}.')
        else:
            self.anounce(f'{method.verb_s} {victim.name}.', f'{method} {victim.name}.')

        self.set_cooldown(method.verb, method.cooldown_time)
        return True

    def act(self):
        super(ActorMutator, self).act()
        self.dec_counter('high', anounce="not high anymore.")  # should be a cooldown as well

    def purge(self):
        if self.actor.max_hitpoints and self.actor.hitpoints < 0:
            self.die()
