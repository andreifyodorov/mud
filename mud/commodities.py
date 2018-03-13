# coding: utf8
from .states import State


class Commodity(State):
    def plural(self, n):
        return self._add_icon(self.abstract_plural % n)

    def __getattribute__(self, attr):
        if attr == "plural" and not hasattr(self, 'abstract_plural'):
            raise AttributeError
        return super(Commodity, self).__getattribute__(attr)

    @property
    def descr(self):
        return self.name


class ActionClasses(object):
    pass


class Edibles(ActionClasses):
    verb = 'eat'


class Vegetable(Commodity, Edibles):
    icon = u'🥕'
    abstract_name = 'a vegetable'
    abstract_plural = '%d vegetables'


class Cotton(Commodity):
    abstract_name = 'cotton'
    abstract_plural = '%d balls of cotton'


conditions = [
    'slightly used',
    'used',
    'well-used',
    'worn out',
    'falling apart',
]

def condition(usage, max_usage):
    """
    >>> condition(1, 3)
    'used'
    >>> condition(2, 3)
    'falling apart'
    >>> condition(1, 5)
    'slightly used'
    >>> condition(2, 5)
    'used'
    >>> condition(3, 5)
    'worn out'
    >>> condition(4, 5)
    'falling apart'
    """
    index = int(round(float(usage) / (max_usage - 1) * (len(conditions) + 1))) - 2
    return conditions[index] if index >= 0 else str()


class Wieldables(ActionClasses):
    verb = 'wield'


class Deteriorates(object):
    def __init__(self):
        self.usages = 0

    @property
    def condition(self):
        s = condition(self.usages, self.max_usages)
        return ' %s' % s if s else s

    @property
    def name_without_icon(self):
        return self.abstract_name % str()

    @property
    def name_with_condition(self):
        return self._add_icon(self.abstract_name % self.condition)

    def plural(self, n):
        return self._add_icon(self.abstract_plural % (n, self.condition))

    @property
    def descr(self):
        return self.name_with_condition


class Spindle(Deteriorates, Commodity, Wieldables):
    max_usages = 3
    abstract_name = 'a%s spindle'
    abstract_plural = '%d%s spindles'


class Shovel(Deteriorates, Commodity, Wieldables):
    max_usages = 5
    abstract_name = 'a%s shovel'
    abstract_plural = '%d%s shovels'


class Wearables(ActionClasses):
    verb = 'wear'


class DirtyRags(Commodity, Wearables):
    icon = u'🧦'
    abstract_name = 'dirty rags'
    abstract_plural = '%d sets of dirty rags'


class RoughspunTunic(Deteriorates, Commodity, Wearables):
    icon = u'👚'
    abstract_name = u'a%s roughspun tunic'
    abstract_plural = '%d%s roughspun tunics'
    max_usages = 50
    deteriorates_into = DirtyRags


class Overcoat(Commodity, Wearables):
    icon = u'🧥'
    abstract_name = 'an overcoat'


class Overalls(Commodity, Wearables):
    icon = u'👖'
    abstract_name = 'overalls'
    abstract_plural = '%d sets of overalls'


class FlamboyantAttire(Commodity, Wearables):
    icon = u'🎩'
    abstract_name = 'flamboyant attire'
