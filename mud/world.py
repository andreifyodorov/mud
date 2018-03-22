from .states import State, PlayerState
from .npcs import NpcState
from .locations import Location, StartLocation, Forests
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

    def all_npcs(self):
        return (a for l in self.values() for a in l.npcs())

    def all_players(self):
        return (a for l in self.values() for a in l.players())

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

        # enact npcs
        npcs = set(self.all_npcs())  # npc can change location
        for npc in npcs:
            npc.get_mutator(self).act()

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

    def npcs(self):
        return self.actors.filter(NpcState)

    def players(self):
        return self.actors.filter(PlayerState)

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors.filter(PlayerState):
            if skip_sender is not None and actor is skip_sender or actor.asleep:
                continue
            actor.send(message)
