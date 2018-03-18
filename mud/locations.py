from random import shuffle
from collections import defaultdict


class Direction(str):
    def __new__(cls, value):
        self = str.__new__(cls, value)
        self.opposite = None
        return self

    @classmethod
    def pair(cls, direction, opposite):
        direction = cls(direction)
        opposite = cls(opposite)
        direction.opposite = opposite
        opposite.opposite = direction
        return direction, opposite


north, south = Direction.pair('north', 'south')
west, east = Direction.pair('west', 'east')
enter, exit = Direction.pair('enter', 'exit')

Direction.compass = (north, west, south, east)
Direction.all = Direction.compass + (enter, exit)


class Location(object):
    all = {}

    def __init__(self, id, name, descr):
        if id in self.all:
            raise Exception('Location %s exists' % id)
        self.id = id
        self.name = name
        self.descr = descr
        if not hasattr(type(self), 'exits'):
            self.exits = {}
        self.all[id] = self

    def to(self, destination, direction, descr_to, descr_back):
        self.add_exit(direction, descr_to, destination)
        destination.add_exit(direction.opposite, descr_back, self)

    def add_exit(self, direction, descr, location):
        self.exits[direction] = dict(descr=descr, location=location)

    def get_exit_groups(self):
        bydescr = defaultdict(list)
        for d, x in self.exits.items():
            bydescr[x["descr"]].append(d)

        for d in Direction.compass:
            if d not in self.exits:
                continue
            descr = self.exits[d]["descr"]
            if len(bydescr[descr]) == 1:
                del bydescr[descr]
                yield descr, [d]

        for descr, ds in bydescr.items():
            yield descr, ds


StartLocation = Field = Location('loc_field', '🌾 a field', 'in a middle of 🌾 a field.')


class ForestLocation(Location):
    pass


class MagicForestLocation(ForestLocation):
    @property
    def exits(self):
        exits = [l for l in Location.all.values() if isinstance(l, ForestLocation)]
        shuffle(exits)
        exits = iter(exits)
        return {d: dict(location=next(exits), descr="You can go %s.") for d in Direction.compass}


Forests = dict()
for direction in Direction.compass:
    Forests[direction] = MagicForestLocation(
        "loc_%s_forest" % direction, "a forest", "lost in a forest.")


Woods = dict()
for direction in Direction.compass:
    if direction in Field.exits:
        continue
    woods = ForestLocation("loc_%s_woods" % direction, "woods", "in woods.")
    Woods[direction] = woods
    Field.to(woods, direction,
             "To the %s you see woods.",
             "To the %s you see 🌾 a field.")
    for direction in Direction.compass:
        if direction not in woods.exits:
            woods.add_exit(direction, "To the %s you see a forest.", Forests[direction])


Village = Location('loc_village', 'a village', 'in a village.')

Field.to(Village, north,
         'To the %s you see a road leading to a village.',
         'To the %s you see 🌾 a field.')

VillageHouse = Location('loc_v_house', 'a log house', "inside a peasant house.")

Village.to(VillageHouse, enter,
           "You see a group of log houses. You can %s one of them.",
           "You can %s a house.")

TownGate = Location('loc_gate', "⛩ a town gate", "at ⛩ a town gate.")

Village.to(TownGate, north,
           "To the %s you see a town wall. A road leads to ⛩ a gate.",
           'To the %s you see a village.')

MarketSquare = Location('loc_market_square', 'a market square', 'on a market square.')

TownGate.to(MarketSquare, north,
            'Through a gate to the %s you see a market square.',
            'To the %s you see ⛩ a gate that leads outside the city.')

FactoryDistrict = Location('loc_factory_dist', 'factory district', 'in a factory district.')

MarketSquare.to(FactoryDistrict, west,
                'To the %s you see a factory district.',
                'To the %s you see a market square.')

Factory = Location('loc_factory', '🏭 a factory', '🏭 in a factory.')

FactoryDistrict.to(Factory, enter,
                   'You can %s 🏭 a factory building.',
                   'You can %s a factory.')

Slums = Location('loc_slum', 'slums', 'in a slum area.')

FactoryDistrict.to(Slums, south,
                   'To the %s you see slums.',
                   'To the %s you see a factory.')
