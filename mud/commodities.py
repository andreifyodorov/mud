from .attacks import Bash
from .states import State
from .utils import condition, Verb


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
    @classmethod
    def all(cls):
        return cls.__subclasses__()


class Edibles(ActionClasses):
    verb = Verb('eat', third='eats')


class Vegetable(Commodity, Edibles):
    icon = '🥕'
    abstract_name = 'a vegetable'
    abstract_plural = '%d vegetables'


class Mushroom(Commodity, Edibles):
    icon = '🍄'
    abstract_name = 'a mushroom'
    abstract_plural = '%d mushrooms'


class Cotton(Commodity):
    icon = '☁️'
    abstract_name = 'cotton'
    abstract_plural = '%d balls of cotton'


class Wieldables(ActionClasses):
    verb = Verb('wield', third='wields')


class Deteriorates(object):
    conditions = [
        'slightly used',
        'used',
        'well-used',
        'worn out',
        'falling apart',
    ]

    def __init__(self):
        self.usages = 0

    @property
    def condition(self):
        s = condition(self.usages, self.max_usages, self.conditions)
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

    @property
    def deteriorate(self):
        """
        >>> Spindle().deteriorate
        'spindle disintegrates.'

        >>> RoughspunTunic().deteriorate
        'old roughspun tunic turns into dirty rags.'

        >>> Test = type('Test', (Commodity, Deteriorates), dict(abstract_name='object'))
        >>> Test().deteriorate
        'object disintegrates.'

        >>> Foobar = type('Foobar', (Commodity, Deteriorates),
        ...               dict(abstract_name='foobar', deteriorates_into=Test))
        >>> Foobar().deteriorate
        'foobar deteriorates into object.'

        """

        if hasattr(self, 'deteriorates_into'):
            into = self.deteriorates_into.abstract_name
            if hasattr(self, 'deteriorate_message'):
                return self.deteriorate_message % into
            else:
                return f"{self.name} deteriorates into {into}."
        else:
            if hasattr(self, 'deteriorate_message'):
                return self.deteriorate_message
            else:
                return f"{self.name} disintegrates."


class Spindle(Deteriorates, Commodity, Wieldables):
    icon = '🌀'
    max_usages = 3
    abstract_name = 'a%s spindle'
    abstract_plural = '%d%s spindles'
    deteriorate_message = 'spindle disintegrates.'


class Weapon(object):
    pass


class Shovel(Deteriorates, Commodity, Wieldables, Weapon):
    max_usages = 5
    abstract_name = 'a%s shovel'
    abstract_plural = '%d%s shovels'
    deteriorate_message = 'shovel falls apart.'
    attack = Bash


class Wearables(ActionClasses):
    verb = Verb('wear', third='wears')


class DirtyRags(Commodity, Wearables):
    icon = '🧦'
    abstract_name = 'dirty rags'
    abstract_plural = '%d sets of dirty rags'


class RoughspunTunic(Deteriorates, Commodity, Wearables):
    icon = '👚'
    abstract_name = 'a%s roughspun tunic'
    abstract_plural = '%d%s roughspun tunics'
    max_usages = 50
    deteriorates_into = DirtyRags
    deteriorate_message = 'old roughspun tunic turns into %s.'


class Overcoat(Commodity, Wearables):
    icon = '🧥'
    abstract_name = 'an overcoat'


class Overalls(Commodity, Wearables):
    icon = '👖'
    abstract_name = 'overalls'
    abstract_plural = '%d sets of overalls'


class FlamboyantAttire(Commodity, Wearables):
    icon = '🎩'
    abstract_name = 'flamboyant attire'
