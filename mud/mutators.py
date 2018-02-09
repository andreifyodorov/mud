def pretty_list(items):
    items = sorted(items, key=lambda item: item.name)
    if len(items) == 0:
        return 'nothing'
    if len(items) == 1:
        item, = items
        return item.name
    return "%s and %s" % (', '.join(i.name for i in items[:-1]), items[-1].name)


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
        self.location.broadcast("%s %s" % (self.actor.name, message), skip_sender=self.actor)

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

    def _relocate(self, item_or_items, source, destination=None):
        items = set()
        try:
            items.update(item_or_items)
        except TypeError:
            items.add(item_or_items)
        items = items & source
        if items:
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

    def produce(self, means):
        if self.actor.last_success_time == self.world.time:
            return
        fruit = means.produce()
        if fruit is None:
            return
        self.actor.last_success_time = self.world.time
        self.anounce('%ss %s.' % (means.verb, fruit.name))
        self.actor.bag.add(fruit)
        return fruit
