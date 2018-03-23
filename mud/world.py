from .locations import Location, Forests
from .commodities import Commodity, Mushroom
from .utils import FilterSet

from random import choice


class WorldState(dict):
    def __init__(self):
        self.time = 0

    def __getitem__(self, key):
        value = self.get(key, None)
        if value is None:
            if key not in Location.all.keys():
                raise KeyError
            value = self[key] = LocationState()
        return value

    def actors(self):
        return (a for l in self.values() for a in l.actors)

    def spawn(self, cls, where):
        where = self[where.id]
        if issubclass(cls, Commodity):
            item = cls()
            where.items.add(item)
            where.broadcast(f"{item.Name} materializes.")
        else:
            raise Exception(f"Don't know how to spawn {cls}")

    def enact(self):
        self.time = self.time or 0

        # enact actors
        actors = set(self.actors())  # actors can change location
        for actor in actors:
            actor.get_mutator(self).act()

        # mushrooms
        mushrooms = list(c for l in Forests.values() for c in self[l.id].items.filter(Mushroom))
        if not mushrooms:
            self.spawn(Mushroom, choice(list(Forests.values())))

        self.time += 1


class LocationState(object):
    def __init__(self):
        self.items = FilterSet()
        self.actors = FilterSet()
        self.means = FilterSet()

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors:
            if skip_sender is not None and actor is skip_sender or actor.asleep:
                continue
            actor.send(message)
