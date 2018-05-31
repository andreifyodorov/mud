from itertools import chain

from .commodities import Commodity, Edibles, Wearables, Wieldables, Deteriorates, Mushroom
from .production import MeansOfProduction
from .utils import credits, pretty_list, FilterSet


class lazy_action(object):
    def __init__(self, action_cls, *args):
        self.action_cls = action_cls
        self.args = args

    def __get__(self, instance, owner):
        if instance is None:
            return self
        action = self.action_cls.from_mutator(instance, *self.args)
        setattr(instance, action.verb, action)
        return action


class ActorMutator:
    default_wear = None

    def __init__(self, actor, world):
        self.actor = actor
        self.world = world

    @classmethod
    def action(cls, action_name):
        def decorator(action_cls):
            action_cls.verb = action_name
            setattr(cls, action_name, lazy_action(action_cls))
            return action_cls
        return decorator

    @classmethod
    def actions(cls, args):
        def decorator(action_cls):
            for arg in args:
                verb = getattr(arg, 'verb', arg)
                setattr(cls, verb, lazy_action(action_cls, arg))
            return action_cls
        return decorator

    @property
    def location(self):
        return self.world[self.actor.location.id]

    @property
    def others(self):
        return (a for a in self.location.actors if a is not self.actor)

    def say_to(self, actor, message):
        actor.send(f"*{self.actor.Name}*: {message}")

    def announce(self, message, reflect=None, objective=None, possessive=False):
        # TODO: looks like it's possible to move reflect to PlayerMutator
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

    def get_default_cooldown_announces(self):
        queue = {type(self)}
        while queue:
            cls = queue.pop()
            queue.update(cls.__bases__)
            if hasattr(cls, 'cooldown_announce'):
                yield cls.cooldown_announce

    def announce_cooldown(self, counter, is_set, is_new=False, announce=None):
        if announce is None:
            for cooldown_announce in self.get_default_cooldown_announces():
                if counter in cooldown_announce:
                    announces = cooldown_announce[counter]
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

    def coolsdown(self, counter):
        return counter in self.actor.cooldown

    def dec_cooldowns(self):
        for counter in set(self.actor.cooldown):
            self._dec(self.actor.cooldown, counter)

    def act(self):
        self.dec_cooldowns()

    def _relocate_self(self, destination):
        source = self.actor.location
        self.announce('leaves to %s.' % destination.name)
        self.location.actors.remove(self.actor)
        self.actor.location = destination
        self.announce('arrives from %s.' % source.name)
        self.location.actors.add(self.actor)
        self.deteriorate(self.actor.wears)

    def spawn(self, location):
        if not self.actor.location and not self.actor.alive:
            if self.default_wear:
                self.actor.wears = self.default_wear()
            self.actor.alive = True
            self.victim = None
            self.actor.location = location
            self.location.actors.add(self.actor)
            self.announce('materializes.')
            if self.actor.max_hitpoints:
                self.actor.hitpoints = self.actor.max_hitpoints

    def die(self):
        if self.actor.alive:
            self.announce('dies.', 'die.')
            self._relocate_to_slot('wields', None)
            self._relocate_to_slot('wears', None)
            self.drop(self.actor.bag)
            self.location.actors.remove(self.actor)
            self.actor.location = None
            self.actor.alive = False

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
        if (victim.alive
                and victim.location is self.actor.location
                and victim.get_mutator(self.world).accept_attack(self.actor)):
            self.actor.victim = victim
            self.announce(f'attacks {victim.name}.', announce)
            return True
        return False

    def accept_attack(self, attacker):
        if self.actor.victim:
            self.actor.attack_queue.append(attacker)
        else:
            self.actor.victim = attacker
        return True

    def kick(self, method):
        victim = self.actor.victim
        if not victim:
            return False

        if self.coolsdown(method.verb):
            return False

        weapon = self.actor.weapon
        if method.is_weapon_method:
            if not weapon or weapon.attack is not method:
                return False

            self.announce(f'{method.verb_s} {victim.name} with {self.actor.weapon.name}.',
                          f'{method} {victim.name} with {self.actor.weapon.name}.',
                          (f'{method.verb_s} you with {self.actor.weapon.name}.', victim))
            self.deteriorate(weapon)
        else:
            self.announce(f'{method.verb_s} {victim.name}.',
                          f'{method} {victim.name}.',
                          (f'{method.verb_s} you.', victim))

        if victim.max_hitpoints:
            victim.hitpoints -= method.damage

        self.set_cooldown(method.verb, method.cooldown_time)
        return True

    def purge(self):
        if self.actor.max_hitpoints and self.actor.hitpoints < 0:
            self.die()

    def cleanup_victims(self):
        queue = self.actor.attack_queue
        victim = self.actor.victim
        while victim and (
                not victim.alive  # victim's dead
                or not self.actor.alive  # actor's dead
                or victim.location is not self.actor.location):  # someone ran away
            victim = self.actor.victim = queue.pop() if queue else None


class Action(ActorMutator):
    # n_args = 0
    #
    # def get_args(self):
    #     raise NotImplementedError
    #
    # @property
    # def is_available(self):
    #     if self.n_args == 0:
    #         return True
    #     elif self.n_args == 1:
    #         return any(self.get_args())
    #     else:
    #         args_queue = [tuple()]
    #         while args_queue:
    #             args = args_queue.pop()
    #             if len(args) == self.n_args:
    #                 return True
    #             args_queue.extend(args + a for a in self.get_args(*args))
    #     return False
    #
    # @property
    # def is_coolingdown(self):
    #     return False  # TODO: cooldown_group / action_name

    class mutate_failure(Exception):
        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        def __call__(self):
            return self.callback()

    is_available = True
    is_coolingdown = False

    @property
    def is_possible(self):
        return self.is_available and not self.is_coolingdown

    def error_unavailable(self, *args):
        return False

    def error_coolsdown(self, *args):
        return False

    def __call__(self, *args):
        if not self.is_available:
            return self.error_unavailable(*args)
        if self.is_coolingdown:
            return self.error_coolsdown(*args)
        return self.after_checks(*args)

    def after_checks(self, *args):
        try:
            result = self.mutate(*args)
        except self.mutate_failure as failure:
            return failure()
        if result:
            self.on_success(result)
        return self.on_done(result)

    def mutate(self, *args):
        raise NotImplementedError

    def on_success(self, result):
        pass

    def on_done(self, result):
        return result

    @classmethod
    def from_mutator(cls, mutator, *args):
        return cls(*args, mutator.actor, mutator.world)


class ActionWithArgs(Action):
    def get_args(self):
        raise NotImplementedError

    @property
    def is_available(self):
        return any(self.get_args())


@ActorMutator.action("go")
class GoAction(ActionWithArgs):
    def get_args(self):
        return self.actor.location.exits.keys()

    def mutate(self, direction):
        destination = self.actor.location.exits[direction]['location']
        for actor in self.location.actors:
            if (hasattr(actor.mutator_class, 'allow')
                    and not actor.get_mutator(self.world).allow(self.actor, destination)):
                return False
        self._relocate_self(destination)
        return True


class RelocateItemsAction(ActionWithArgs):
    def get_args(self):
        return self.source

    def mutate(self, item_or_items):
        return self._relocate(item_or_items, self.source, self.destination)


@ActorMutator.action("pick")
class PickAction(RelocateItemsAction):
    @property
    def source(self):
        return self.location.items

    @property
    def destination(self):
        return self.actor.bag

    def on_success(self, items):
        self.announce(f"picks up {items}.")


@ActorMutator.action("drop")
class DropAction(RelocateItemsAction):
    @property
    def source(self):
        return self.actor.bag

    @property
    def destination(self):
        return self.location.items

    def on_success(self, items):
        self.announce(f"drops {items} on the ground.")


class ItemAction(ActionWithArgs):
    def get_args(self):
        return set(self.actor.bag.filter(self.action_cls))

    def error_wrong_class(self, item):
        return False

    def mutate(self, item):
        if not isinstance(item, self.action_cls):
            raise self.mutate_failure(lambda: self.error_wrong_class(item))

    def on_success(self, item):
        self.announce(f'{self.verb.third} {item.name}.')


@ActorMutator.action(Edibles.verb)
class EatAction(ItemAction):
    action_cls = Edibles
    cooldown_announce = {'high': {True: "high", False: "not high anymore"}}

    def mutate(self, item):
        super().mutate(item)
        result = self._relocate(item, self.actor.bag)  # _relocate returns a set
        return result.pop() if result else None

    def on_success(self, item):
        super().on_success(item)
        if isinstance(item, Mushroom):
            self.set_cooldown('high', 5)


@ActorMutator.actions((Wearables, Wieldables))
class ItemToSlotAction(ItemAction):
    def __init__(self, action_cls, *args):
        super().__init__(*args)
        self.action_cls = action_cls
        self.verb = action_cls.verb

    def mutate(self, item):
        super().mutate(item)
        if self._relocate_to_slot(self.verb.third, item):
            return item


@ActorMutator.action("unequip")
class UnequipAction(Action):
    @property
    def is_available(self):
        return self.actor.wields is not None

    def mutate(self):
        item = self.actor.wields
        self.actor.wields = None
        self.actor.bag.add(item)
        return item

    def on_success(self, item):
        self.announce(f'puts away {item.name}.')


@ActorMutator.actions(MeansOfProduction.__subclasses__())
class ProduceAction(Action):
    def __init__(self, means_cls, *args):
        self.means_cls = means_cls
        self.verb = means_cls.verb
        super().__init__(*args)

    @property
    def means(self):
        return next(self.location.means.filter(self.means_cls), None)

    @property
    def is_available(self):
        return self.means is not None

    @property
    def is_possible(self):
        missing, tools, materials = self.get_tools_and_materials()
        return False if missing else True

    @property
    def is_coolingdown(self):
        return self.coolsdown('produce')

    def error_missing(self, missing):
        return False

    def on_success(self, fruit_or_fruits):
        self.announce(f"{self.verb.third} {fruit_or_fruits}.")

    def get_tools_and_materials(self):
        means = self.means
        missing = FilterSet()
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
                missing.add(t())
        # get required materials
        materials = {}
        for t, n in means.required_materials.items():
            loc = list(self.actor.bag.filter(t))
            if len(loc) >= n:
                materials[t] = loc[:n]
            else:
                missing.update(t() for _ in range(n - len(loc)))
        # do we miss something?
        return missing, tools, materials

    def mutate(self):
        missing, tools, materials = self.get_tools_and_materials()
        if missing:
            raise self.mutate_failure(lambda: self.error_missing(missing))

        self._relocate(chain.from_iterable(materials.values()), self.actor.bag)

        if tools:
            tool, = tools.values()
            self.wield(tool)
            self.deteriorate(tool)
        else:
            self.unequip()

        # and finally!
        fruit_or_fruits = self.means.produce(tools, materials)
        self.set_cooldown('produce', 1)

        if fruit_or_fruits is None:
            return

        result = FilterSet()
        try:
            result.update(fruit_or_fruits)
        except TypeError:
            result.add(fruit_or_fruits)
        self.actor.bag.update(result)
        return result
