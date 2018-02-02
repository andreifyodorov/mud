#!/usr/bin/env python

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

