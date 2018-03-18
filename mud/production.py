from .commodities import Vegetable, Cotton, Spindle, RoughspunTunic, Shovel
from random import uniform


def weighted_choice(d):
    total = sum(w for x, w in d.items())
    r = uniform(0, total)
    for x, w in d.items():
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
    optional_tools = {Shovel}

    def get_product(self):
        return weighted_choice({Vegetable: 1, Cotton: .1})

    def produce(self, tools, materials):
        result = []
        if tools:
            result.append(self.get_product())
        result.append(self.get_product())
        return result


class Distaff(MeansOfProduction):
    descr = "There's a distaff in the corner. You can %s a yarn."
    verb = 'spin'

    required_tools = {Spindle}
    required_materials = {Cotton: 2}

    def produce(self, tools, materials):
        return RoughspunTunic()


class Workbench(MeansOfProduction):
    descr = "There's a workbench. You can %s something useful."
    verb = 'make'

    def produce(self, tools, materials):
        return Shovel()
