#!/usr/bin/env python

from mud.chatflow import Chatflow, CommandPrefix
from mud.states import World, PlayerState
from mud.locations import StartLocation, Field, VillageHouse, TownGate
from mud.commodities import Vegetable, Cotton, Spindle
from mud.npcs import PeasantState
from migrate import migrations

from colored import fore, style
import re


class MockStorage(object):
    def __init__(self):
        self.world = World()
        self.world.time = 1
        self.players = {}
        self.chatkeys = {}

    def all_players(self):
        return self.players.values()

    def all_npcs(self):
        return self.world.all_npcs()


def output(msg):
    msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
    print fore.YELLOW + msg + style.RESET


def observe(msg):
    print fore.BLUE + msg + style.RESET


def send_callback_factory(chatkey):
    def callback(msg):
        pass
    return callback


if __name__ == '__main__':
    # from storage import Storage
    # storage = Storage(send_callback_factory)
    storage = MockStorage()

    for migrate in migrations:
        migrate(storage)

    player = PlayerState(send_callback=output)
    storage.players[1] = player
    storage.chatkeys[player] = 1
    player.name = 'Andrey'
    player.bag.update([Vegetable(), Cotton(), Cotton(), Cotton(), Cotton()])
    Chatflow(player, storage.world).spawn(Field)

    observer = PlayerState(send_callback=observe)
    storage.players[2] = observer
    storage.chatkeys[observer] = 2
    observer.name = 'A silent observer'
    Chatflow(observer, storage.world).spawn(Field)

    # peasant = PeasantState()
    # peasant.name = 'Jack'
    # peasant.get_mutator(storage.world).spawn(Field)

    storage.world[Field.id].items.update([Vegetable()])


    s = '/where'
    # s = '/start'
    # s = '/restart'
    # s = '/look'
    # s = '/bag'
    # s = '/drop'

    # cmds = ['/barter', '/1', '/1']

    # peasant = next(a for a in storage.world[VillageHouse.id].actors if isinstance(a, PeasantState))

    # for s in cmds:
    while True:
        chatflow = Chatflow(player, storage.world, cmd_pfx=CommandPrefix('/'))
        chatflow.process_message(s)

        try:
            # s = raw_input('%s> ' % ' '.join('/' + c for c, h in chatflow.get_commands()))
            s = raw_input('%s> ' % "")
        except (EOFError, KeyboardInterrupt):
            break

        # break

        if not s:
            storage.world.enact()
            observe("World time: %d" % storage.world.time)
    # storage.print_dump()
