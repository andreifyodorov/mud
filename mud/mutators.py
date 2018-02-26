from itertools import groupby, islice, chain


def pretty_list(item_or_items):
    if hasattr(item_or_items, 'name'):
        return item_or_items.name

    items = item_or_items

    if len(items) == 0:
        return 'nothing'

    if len(items) == 1:
        item, = items
        return item.name

    items = sorted(items, key=lambda item: item.name)
    names = list(pretty_names(items))

    if len(names) == 1:
        name, = names
        return name

    return "%s and %s" % (', '.join(n for n in names[:-1]), names[-1])


def pretty_names(items):
    for name, group in groupby(items, lambda i: i.name):
        group = list(group)

        if len(group) == 1:
            item, = group
            yield item.name
            continue

        for item in group:
            if hasattr(item, 'plural'):
                l = len(list(group))
                if callable(item.plural):
                    yield item.plural(l)
                else:
                    yield item.plural % l
                break
            yield item.name


class ExitGuardMixin(object):
    pass


class StateMutator(object):
    def __init__(self, actor, world):
        self.actor = actor
        self.world = world

    @property
    def location(self):
        return self.world[self.actor.location.id]

    def anounce(self, message):
        self.location.broadcast("%s %s" % (self.actor.Name, message), skip_sender=self.actor)

    def say_to(self, actor, message):
        actor.send("*%s*: %s" % (self.actor.Name, message))

    def spawn(self, location):
        if not self.actor.location and not self.actor.alive:
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

        guards = (a for a in self.location.actors if isinstance(a, ExitGuardMixin))
        for guard in guards:
            if not guard.get_mutator(self.world).allow(self.actor, new):
                return False

        self.anounce('leaves to %s.' % new.name)
        self.location.actors.remove(self.actor)
        self.actor.location = new
        self.anounce('arrives from %s.' % old.name)
        self.location.actors.add(self.actor)
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

    def wear(self, item):
        if self.actor.wears is not None:
            self.actor.bag.add(self.actor.wears)
        items = self._relocate(item, self.actor.bag)
        if items:
            self.actor.wears, = items
        return items

    def barter(self, counterparty, what, for_what):
        if (counterparty.barters
                and counterparty.get_mutator(self.world).accept_barter(self.actor, what, for_what)):
            self.anounce('barters %s for %s with %s.'
                         % (pretty_list(what), pretty_list(for_what), counterparty.name))
            return True
        return False

    def accept_barter(self, counterparty, what, for_what):
        self._relocate(what, counterparty.bag, self.actor.bag)
        self._relocate(for_what, self.actor.bag, counterparty.bag)
        return True

    def _items_by_class(self, cls):
        return (i for i in self.actor.bag if isinstance(i, cls))


    def produce(self, means, missing=None):
        if missing is None:
            missing = []
        # get required/optional tools
        tools = {}
        for t in means.optional_tools | means.required_tools:
            tool = next(self._items_by_class(t), None)
            if tool:
                tools[t] = tool
            elif t in means.required_tools:
                missing.append(t)
        # get required materials
        materials = {}
        for t, n in means.required_materials.iteritems():
            l = list(self._items_by_class(t))
            if len(l) >= n:
                materials[t] = l[:n]
            else:
                missing.extend([t] * (n - len(l)))
        # do we miss something?
        if missing:
            return
        # not too often
        if self.actor.last_success_time == self.world.time:
            return
        # remove materials from the world
        self._relocate(chain.from_iterable(materials.itervalues()), self.actor.bag)
        # be fruitful
        fruit = means.produce(tools, materials)
        if fruit is None:
            return

        self.actor.last_success_time = self.world.time
        self.anounce('%ss %s.' % (means.verb, fruit.name))
        self.actor.bag.add(fruit)

        return fruit
