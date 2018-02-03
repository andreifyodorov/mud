from commodities import Vegetable, Cotton
from random import choice


class MeansOfProduction(object):
    pass


class Land(MeansOfProduction):
    descr="The land seems arable to %s."
    verb='farm'

    def produce(self):
        return choice([Vegetable, Cotton])()


class Factory(MeansOfProduction):
    pass
