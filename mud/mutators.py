from .commodities import Commodity, Wearables, Wieldables, Deteriorates, Mushroom
from .utils import credits, pretty_list, FilterSet
from itertools import chain


class StateMutator(object):
    def __init__(self, actor):
        self.actor = actor

    def announce(self, message):
        raise NotImplementedError

    def announce_cooldown(self, counter, is_set, is_new=False, announce=None):
        if announce is None:
            queue = {type(self)}
            while queue:
                cls = queue.pop()
                queue.update(cls.__bases__)
                if not hasattr(cls, 'cooldown_announce'):
                    continue
                if counter in cls.cooldown_announce:
                    announces = cls.cooldown_announce[counter]
                    key = 'first' if is_set and is_new and 'first' in announces else is_set
                    announce = announces.get(key)
                    break

        if announce:
            if isinstance(announce, tuple):
                self.announce(*announce)
            else:
                self.announce(f"is {announce}.", f"are {announce}.")

    def _set(self, counters, counter, value, announce=None):
        if value > 0:
            is_new = counter not in counters
            counters[counter] = value - 1  # first change, then announce (wake up)
            self.announce_cooldown(counter, is_set=True, is_new=is_new, announce=announce)
            return True
        return False

    def _dec(self, counters, counter, announce=None):
        value = counters.get(counter, None)
        if value is not None and value > 0:
            counters[counter] = value - 1
            return False
        else:
            if value is not None:
                self.announce_cooldown(counter, is_set=False, announce=announce)  # first announce, then delete (sleep)
                del counters[counter]
            return True

    def set_cooldown(self, counter, value, announce=None):
        return self._set(self.actor.cooldown, counter, value, announce)

    def dec_cooldowns(self):
        for counter in set(self.actor.cooldown):
            self._dec(self.actor.cooldown, counter)

    def coolsdown(self, counter):
        return counter in self.actor.cooldown

    def act(self):
        self.dec_cooldowns()


class ActorMutator(StateMutator):
    default_wear = None
    cooldown_announce = {
        'high': {True: "high", False: "not high anymore"}}

    def __init__(self, actor, world):
        super().__init__(actor)
        self.world = world

    @property
    def location(self):
        return self.world[self.actor.location.id]

    @property
    def others(self):
        return (a for a in self.location.actors if a is not self.actor)

    def announce(self, message, reflect=None, objective=None, possessive=False):
        skip_senders = {self.actor}
        if not possessive:
            you, them = "You", self.actor.Name
        else:
            you, them = "Your", f"{self.actor.Name}'s"
        # reflect message is sent to the sender itself (e.g. "You attack rat")
        if reflect and self.actor.recieves_announces:
            if reflect is True:
                reflect = message
            self.actor.send(f"{you} {reflect}")
        # objective message (if present) is sent to the target of announced action (e.g. "Rat attacks you")
        if objective:
            objective, target_actor = objective
            if target_actor.recieves_announces:
                target_actor.send(f"{them} {objective}")
            skip_senders.add(target_actor)
        # the message itself is broadcast
        self.location.broadcast(f"{them} {message}", skip_senders=skip_senders)

    def say_to(self, actor, message):
        actor.send(f"*{self.actor.Name}*: {message}")

    def spawn(self, location):
        if not self.actor.location and not self.actor.alive:
            if self.default_wear:
                self.actor.wears = self.default_wear()
            self.actor.alive = True
            self.actor.hitpoints = self.actor.max_hitpoints
            self.victim = None
            self.actor.location = location
            self.location.actors.add(self.actor)
            self.announce('materializes.')

    def die(self):
        if self.actor.alive:
            self.announce('dies.', 'die.')
            self._relocate_to_slot('wields', None)
            self._relocate_to_slot('wears', None)
            self.drop(self.actor.bag)
            self.location.actors.remove(self.actor)
            self.actor.location = None
            self.actor.alive = False

    def go(self, direction):
        destination = self.actor.location.exits[direction]['location']
        for actor in self.location.actors:
            if (hasattr(actor.mutator_class, 'allow')
                    and not actor.get_mutator(self.world).allow(self.actor, destination)):
                return False
        return self._relocate_self(destination)

    def _relocate_self(self, destination):
        source = self.actor.location
        self.announce('leaves to %s.' % destination.name)
        self.location.actors.remove(self.actor)
        self.actor.location = destination
        self.announce('arrives from %s.' % source.name)
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

    def pick(self, item_or_items, announce=None):
        items = self._relocate(item_or_items, self.location.items, self.actor.bag)
        if items:
            items_str = pretty_list(items)
            self.announce(f'picks up {items_str}.', announce and announce(items_str))
        return items

    def drop(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag, self.location.items)
        if items:
            items_str = pretty_list(items)
            self.announce(f'drops {items_str} on the ground.', f'drop {items_str} on the ground.')
        return items

    def eat(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag)
        if items:
            items_str = pretty_list(items)
            self.announce(f'eats {items_str}.', f'eat {items_str}.')
        if any(items.filter(Mushroom)):
            self.set_cooldown('high', 5)
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
            self.announce(f'wears {item.name}.', f'wear {item.name}.')
            return item

    def wield(self, item):
        if isinstance(item, Wieldables) and self._relocate_to_slot('wields', item):
            self.announce(f'wields {item.name}.', f'wield {item.name}.')
            return item

    def unequip(self, announce=None):
        item = self.actor.wields
        if item:
            self.announce(f'puts away {item.name}.', announce and announce(item))
            self._relocate_to_slot('wields', None)
            return item

    def barter(self, counterparty, what, for_what):
        if (counterparty.barters
                and counterparty.get_mutator(self.world).accept_barter(self.actor, what, for_what)):
            announce = f"{pretty_list(what)} for {pretty_list(for_what)} with {counterparty.name}"
            self.announce(f'barters {announce}.', f'barter {announce}.')

    def accept_barter(self, counterparty, what, for_what):
        return (
            self._relocate(what, counterparty.bag, self.actor.bag)
            and self._relocate(for_what, self.actor.bag, counterparty.bag))

    def _make_transaction(self, verb, prep, counterparty, what, price, source, destination):
        if self._relocate(what, source, destination):
            self.actor.credits -= price
            counterparty.credits += price
            announce = f"{pretty_list(what)} {prep} {counterparty.name}"
            self.announce(f'{verb}s {announce}.', f'{verb} {announce} for {credits(abs(price))}.')

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
        self.announce('%ss %s.' % (means.verb, pretty_list(fruits)))
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

        self.announce(commodity.deteriorate, reflect=True, possessive=True)

        return True

    def attack(self, victim, announce=None):
        self.actor.victim = victim
        if victim.victim is None:
            victim.victim = self.actor
        self.announce(f'attacks {victim.name}.', announce)

    def kick(self, method):
        victim = self.actor.victim
        if not victim:
            return False

        if self.coolsdown(method.verb):
            return False

        if victim.max_hitpoints:
            victim.hitpoints -= method.damage

        if method.is_weapon_method:
            weapon = self.actor.weapon
            if weapon.attack is not method:
                return False
            self.announce(f'{method.verb_s} {victim.name} with {self.actor.weapon.name}.',
                          f'{method} {victim.name} with {self.actor.weapon.name}.',
                          (f'{method.verb_s} you with {self.actor.weapon.name}.', victim))
            self.deteriorate(weapon)
        else:
            self.announce(f'{method.verb_s} {victim.name}.',
                          f'{method} {victim.name}.',
                          (f'{method.verb_s} you.', victim))

        self.set_cooldown(method.verb, method.cooldown_time)
        return True

    def purge(self):
        if self.actor.max_hitpoints and self.actor.hitpoints < 0:
            self.die()

    def cleanup_victims(self):
        victim = self.actor.victim
        if victim and (
                not victim.alive  # victim's dead
                or not self.actor.alive  # actor's dead
                or victim.location is not self.actor.location):  # someone ran away
            if victim.victim is self.actor:
                victim.victim = None
            self.actor.victim = None
