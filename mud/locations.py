# coding: utf8

class Location(object):
    all = {}

    def __init__(self, id, name, descr):
        if id in self.all:
            raise Exception('Location %s exists' % id)
        self.id = id
        self.name = name
        self.descr = descr
        self.exits = {}

        self.all[id] = self

    def add_exit(self, direction, **kwargs):
        self.exits[direction] = kwargs


StartLocation = Field = Location(
    id='loc_field',
    name='a field',
    descr='in a middle of a field.')

Village = Location(
    id='loc_village',
    name='a village',
    descr='in a village.')

Field.add_exit(
    direction='north',
    descr='To the %s you see a road leading to a village.',
    location=Village)

Village.add_exit(
    direction='south',
    descr='To the %s you see a field.',
    location=Field)

VillageHouse = Location(
    id='loc_v_house',
    name='a log house',
    descr="inside a peasant house.")

Village.add_exit(
    direction='enter',
    descr="You see a group of log houses. You can %s one of them.",
    location=VillageHouse)

VillageHouse.add_exit(
    direction='exit',
    descr="You can %s a house.",
    location=Village)

TownGate = Location(
    id='loc_gate',
    name=u"⛩ a town gate",
    descr=u"at ⛩ a town gate.")

Village.add_exit(
    direction='north',
    descr=u"To the %s you see a town wall. A road leads to ⛩ a gate.",
    location=TownGate)

TownGate.add_exit(
    direction='south',
    descr='To the %s you see a village.',
    location=Village)

MarketSquare = Location(
    id='loc_market_square',
    name='a market square',
    descr='on a market square.')

TownGate.add_exit(
    direction='north',
    descr='Through a gate to the %s you see a market square.',
    location=MarketSquare)

MarketSquare.add_exit(
    direction='south',
    descr=u'To the %s you see ⛩ a gate that leads outside the city.',
    location=TownGate)

FactoryDistrict = Location(
    id='loc_factory_dist',
    name='factory district',
    descr='in a factory district.')

MarketSquare.add_exit(
    direction='west',
    descr='To the %s you see a factory district.',
    location=FactoryDistrict)

FactoryDistrict.add_exit(
    direction='east',
    descr='To the %s you see a market square.',
    location=MarketSquare)

Factory = Location(
    id='loc_factory',
    name=u'🏭 a factory',
    descr=u'🏭 in a factory.')

FactoryDistrict.add_exit(
    direction='north',
    descr=u'To the %s you see an entrance to 🏭 a factory building.',
    location=Factory)

Factory.add_exit(
    direction='exit',
    descr=u'You can %s a factory.',
    location=FactoryDistrict)

Slums = Location(
    id='loc_slum',
    name=u'slums',
    descr=u'in a slum area.')

FactoryDistrict.add_exit(
    direction='south',
    descr=u'To the %s you see slums.',
    location=Slums)

Slums.add_exit(
    direction='north',
    descr=u'To the %s you see a factory.',
    location=FactoryDistrict)


