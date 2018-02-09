from commodities import Vegetable, Cotton
from random import uniform


class MeansOfProduction(object):
    pass


class Land(MeansOfProduction):
    descr = "The land seems arable to %s."
    verb = 'farm'
    outcome = [(Vegetable, 1), (Cotton, .1)]

    def produce(self):
        total = sum(w for c, w in self.outcome)
        r = uniform(0, total)
        for c, w in self.outcome:
            if w >= r:
                return c()
            r -= w


class Factory(MeansOfProduction):
    pass
