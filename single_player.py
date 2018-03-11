#!/usr/bin/env python

from mud.chatflow import Chatflow, CommandPrefix
from mud.states import World, PlayerState
from mud.locations import StartLocation, Field, VillageHouse, TownGate, MarketSquare
from mud.commodities import Vegetable, Cotton, Spindle, DirtyRags
from mud.npcs import PeasantState
from test import MockRedis
from storage import Storage
from migrate import migrations

from colored import fore, style
import re


PLAYER_CHATKEY = 1
OBSERVER_CHATKEY = 2

def send_callback_factory(chatkey):
    if chatkey == PLAYER_CHATKEY:
        def output(msg):
            msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
            print fore.YELLOW + msg + style.RESET
        return output

    def observe(msg):
        print fore.BLUE + msg + style.RESET
    return observe


if __name__ == '__main__':
    storage = Storage(send_callback_factory, redis=MockRedis())

    for migrate in migrations:
        # print "Apply migration %s" % migrate
        migrate(storage)

    player = storage.get_player_state(PLAYER_CHATKEY)
    player.name = 'Andrey'
    player.bag.update([Vegetable(), Cotton(), Cotton(), DirtyRags(), DirtyRags()])
    Chatflow(player, storage.world).spawn(MarketSquare)

    observer = storage.get_player_state(OBSERVER_CHATKEY)
    observer.name = 'A silent observer'
    Chatflow(observer, storage.world).spawn(MarketSquare)

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
        chatflow = Chatflow(player, storage.world, cmd_pfx=CommandPrefix('/'))
        chatflow.process_message(s)

        try:
            # s = raw_input('%s> ' % ' '.join('/' + c for c, h in chatflow.get_commands()))
            s = raw_input('%s> ' % ((player.input, player.chain),))
        except (EOFError, KeyboardInterrupt):
            break

        # break

        if not s:
            storage.world.enact()
            observe("World time: %d" % storage.world.time)
    # storage.print_dump()
