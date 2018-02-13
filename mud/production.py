from commodities import Vegetable, Cotton, Spindle, RoughspunTunic
from random import uniform


def weighted_choice(d):
    total = sum(w for x, w in d.iteritems())
    r = uniform(0, total)
    for x, w in d.iteritems():
        if w >= r:
            return x()
        r -= w


class MeansOfProduction(object):
    optional_tools = set()
    required_tools = set()
    required_materials = {}


class Land(MeansOfProduction):
    descr = "The land seems arable to %s."
    verb = 'farm'

    def produce(self, tools, materials):
        tools.clear()
        return weighted_choice({Vegetable: 1, Cotton: .1})


class Distaff(MeansOfProduction):
    descr = "There's a distaff in the corner. You can %s a yarn."
    verb = 'spin'

    required_tools = {Spindle}
    required_materials = {Cotton: 2}

    def produce(self, tools, materials):
        return RoughspunTunic()


class Factory(MeansOfProduction):
    pass
