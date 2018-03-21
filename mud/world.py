from .states import State, NpcState, PlayerState
from .locations import Location
from .utils import FilterSet


class World(dict):
    def __init__(self):
        self.time = 0

    def __getitem__(self, key):
        value = self.get(key, None)
        if value is None:
            if key not in Location.all.keys():
                raise KeyError
            value = self[key] = WorldState()
        return value

    def all_npcs(self):
        return (a for l in self.values() for a in l.actors.filter(NpcState))

    def all_players(self):
        return (a for l in self.values() for a in l.actors.filter(PlayerState))

    def enact(self):
        self.time = self.time or 0
        npcs = set(self.all_npcs())  # npc can change location
        for npc in npcs:
            npc.get_mutator(self).act()
        self.time += 1


class WorldState(State):
    def __init__(self):
        super(WorldState, self).__init__()
        self.items = FilterSet()
        self.actors = FilterSet()
        self.means = FilterSet()

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors.filter(PlayerState):
            if skip_sender is not None and actor is skip_sender or actor.asleep:
                continue
            actor.send(message)
