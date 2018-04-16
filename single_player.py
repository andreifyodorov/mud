#!/usr/bin/env python

import re
import pprint
import sys

from mud.player import PlayerState, Chatflow, CommandPrefix  # noqa: F401
from mud.locations import StartLocation, Location, Field, VillageHouse, TownGate, MarketSquare  # noqa: F401
from mud.commodities import Vegetable, Mushroom, Cotton, Spindle, DirtyRags, Shovel, RoughspunTunic  # noqa: F401
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
    redis = MockRedis()
    storage = Storage(send_callback_factory, redis=redis, cmd_pfx=cmd_pfx)

    for migrate in migrations:
        # print "Apply migration %s" % migrate
        migrate(storage)

    player = storage.get_player_state(PLAYER_CHATKEY)
    # player.name = 'Andrey'
    # player.bag.update([Shovel(), Mushroom(), RoughspunTunic()])
    # Chatflow(player, storage.world).spawn(StartLocation)

    observer = storage.get_player_state(OBSERVER_CHATKEY)
    observer.name = 'A silent observer'
    Chatflow(observer, storage.world).spawn(StartLocation)

    # peasant = PeasantState()
    # peasant.name = 'Jack'
    # peasant.get_mutator(storage.world).spawn(Field)

    storage.world[Field.id].items.update([Vegetable(), Spindle()])
    storage.save()

    # s = '/where'
    s = '/start'
    # s = '/restart'
    # s = '/look'
    # s = '/bag'
    # s = '/drop'
    # s = '/barter'

    cmds = sys.argv[1:] if len(sys.argv) > 1 else [s]

    # peasant = next(a for a in storage.world[VillageHouse.id].actors if isinstance(a, PeasantState))

    # while storage.world.time < 517:
    #     storage.world.enact()
    #     observe("World time: %d" % storage.world.time)

    # for s in cmds:
    while True:
        if cmds:
            s = cmds.pop(0)
            print(f"> {s}")

        current_dump = dict(storage.dump())
        if not s or s == "--":
            storage.world.enact()
            observe("World time: %d" % storage.world.time)
        else:
            chatflow = Chatflow(player, storage.world, cmd_pfx=cmd_pfx)
            chatflow.process_message(s)

        print(fore.DARK_GRAY
              + pprint.pformat(DeepDiff(current_dump, dict(storage.dump()), verbose_level=2), width=120)
              + style.RESET)

        print(fore.DARK_GREEN
              + repr(
                  {cat: [n for n, f in commands] for cat, commands in chatflow.get_commands_by_category().items()})
              + style.RESET)

        if cmds:
            continue

        try:
            s = input(f'> ')
        except (EOFError, KeyboardInterrupt):
            break
