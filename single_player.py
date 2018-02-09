#!/usr/bin/env python

from mud.chatflow import Chatflow
from mud.states import World, PlayerState
from mud.locations import StartLocation, TownGate
from mud.commodities import Vegetable, Cotton
from migrate import migrations

from colored import fore, style
import re


class MockStorage(object):
    def __init__(self):
        self.world = World()

    def all_players(self):
        return ()


def output(msg):
    msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
    print fore.YELLOW + msg + style.RESET


def observe(msg):
    print fore.BLUE + msg + style.RESET


if __name__ == '__main__':
    storage = MockStorage()
    for migrate in migrations:
        migrate(storage)

    player = PlayerState(send_callback=output)
    player.name = 'Andrey'
    player.bag.update([Vegetable(), Cotton()])
    Chatflow(player, storage.world).spawn(TownGate)

    observer = PlayerState(send_callback=observe)
    Chatflow(player, storage.world).spawn(TownGate)
    observer.name = 'A silent observer'

    s = '/where'
    # s = '/start'

    while True:
        chatflow = Chatflow(player, storage.world, command_prefix='/')
        chatflow.process_message(s)

        try:
            # s = raw_input('%s> ' % ' '.join('/' + c for c, h in chatflow.get_commands()))
            s = raw_input('%s> ' % player.last_success_time)
        except (EOFError, KeyboardInterrupt):
            break

        if not s:
            storage.world.enact()
            observe("World time: %d" % storage.world.time)
