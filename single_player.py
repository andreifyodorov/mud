#!/usr/bin/env python

import re
import pprint

from mud.player import PlayerState, Chatflow, CommandPrefix  # noqa: F401
from mud.locations import StartLocation, Location, Field, VillageHouse, TownGate, MarketSquare  # noqa: F401
from mud.commodities import Vegetable, Mushroom, Cotton, Spindle, DirtyRags, Shovel  # noqa: F401
from mud.npcs import PeasantState  # noqa: F401
from test import MockRedis
from storage import Storage
from migrate import migrations

from colored import fore, style
from deepdiff import DeepDiff


PLAYER_CHATKEY = 1
OBSERVER_CHATKEY = 2


def output(msg):
    msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
    print(fore.YELLOW + msg + style.RESET)


def observe(msg):
    print(fore.BLUE + msg + style.RESET)


def send_callback_factory(chatkey):
    if chatkey == PLAYER_CHATKEY:
        return output
    return observe


if __name__ == '__main__':
    cmd_pfx = CommandPrefix('/')
    storage = Storage(send_callback_factory, redis=MockRedis(), cmd_pfx=cmd_pfx)

    for migrate in migrations:
        # print "Apply migration %s" % migrate
        migrate(storage)

    player = storage.get_player_state(PLAYER_CHATKEY)
    player.name = 'Andrey'
    player.bag.update([Shovel(), Mushroom()])
    Chatflow(player, storage.world).spawn(StartLocation)

    observer = storage.get_player_state(OBSERVER_CHATKEY)
    observer.name = 'A silent observer'
    Chatflow(observer, storage.world).spawn(Location.all[player.location.id])

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
    # s = '/barter'

    # cmds = ['/barter', '/1', '/1']

    # peasant = next(a for a in storage.world[VillageHouse.id].actors if isinstance(a, PeasantState))

    # while storage.world.time < 517:
    #     storage.world.enact()
    #     observe("World time: %d" % storage.world.time)

    # for s in cmds:
    while True:
        current_dump = dict(storage.dump())
        if s:
            chatflow = Chatflow(player, storage.world, cmd_pfx=cmd_pfx)
            chatflow.process_message(s)
        else:
            storage.world.enact()
            observe("World time: %d" % storage.world.time)

        print(fore.DARK_GRAY
              + pprint.pformat(DeepDiff(current_dump, dict(storage.dump()), verbose_level=2), width=120)
              + style.RESET)

        try:
            s = input(f'> ')
        except (EOFError, KeyboardInterrupt):
            break
