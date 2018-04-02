from itertools import chain

from .locations import Location, Field, Woods, Forests
from .commodities import Commodity, Mushroom
from .npcs import NpcState, RatState
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
        if issubclass(cls, Commodity):
            item = cls()
            where = self[where.id]
            where.items.add(item)
            where.broadcast(f"{item.Name} materializes.")
        elif issubclass(cls, NpcState):
            npc = cls()
            npc.get_mutator(self).spawn(where)
        else:
            raise Exception(f"Don't know how to spawn {cls}")

    def enact(self):
        self.time = self.time or 0

        # enact actors
        # actors can change location so take a set
        mutators = set(a.get_mutator(self) for a in self.actors())
        for mutator in mutators:
            mutator.act()
        for mutator in mutators:
            mutator.purge()

        # mushrooms
        mushrooms = list(c for l in Forests.values() for c in self[l.id].items.filter(Mushroom))
        if not mushrooms:
            self.spawn(Mushroom, choice(list(Forests.values())))

        # rat
        rat_locations = set(chain([Field], Woods.values()))
        if not any(chain.from_iterable(self[loc.id].actors.filter(RatState) for loc in rat_locations)):
            self.spawn(RatState, choice(list(Woods.values())))

        self.time += 1


class LocationState(object):
    def __init__(self):
        self.items = FilterSet()
        self.actors = FilterSet()
        self.means = FilterSet()

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors:
            if skip_sender is not None and actor is skip_sender or not actor.recieves_announces:
                continue
            actor.send(message)
