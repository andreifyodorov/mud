# coding: utf8

class Commodity(object):
    pass


class ActionClasses(object):
    pass


class Edibles(ActionClasses):
    verb = 'eat'


class Vegetable(Commodity, Edibles):
    name = u'🥕 a vegetable'
    plural = '%d vegetables'


class Shovel(Commodity):
    name = 'a shovel'
    plural = '%d shovels'


class Cotton(Commodity):
    name = 'cotton'
    plural = '%d balls of cotton'


class Spindle(Commodity):
    name = 'a spindle'


class Wearables(ActionClasses):
    verb = 'wear'


class DirtyRags(Commodity, Wearables):
    name = u'🧦 dirty rags'


class RoughspunTunic(Commodity, Wearables):
    name = u'👚 a roughspun tunic'


class Overcoat(Commodity, Wearables):
    name = u'🧥 an overcoat'