#!/usr/bin/env python
# coding: utf8

from mud.chatflow import Chatflow
from mud.locations import Field, TownGate, VillageHouse
from mud.production import Land, Distaff
from mud.states import PlayerState
from mud.npcs import PeasantState, GuardState
from mud.commodities import Spindle, DirtyRags, RoughspunTunic, Overcoat

from bot import bot
from storage import Storage


migrations = list()

def version(f):
    migrations.append(f)
    return f


@version
def migrate_1(storage):
    for player in storage.all_players():
        player.send("Game updated to version 1. Sorry for killing everyone, guys")

        mutator = Chatflow(player, storage.world, bot.cmd_pfx)

        if player.name == 'Player':
            mutator.die()
            player.name = None
            mutator.process_message('%sstart' % bot.cmd_pfx)

    if not storage.world[Field.id].means:
        storage.world[Field.id].means.add(Land())


@version
def migrate_2(storage):
    for player in storage.all_players():
        player.send("Game updated to version 2. Welcome a hungry and lazy peasant!")

    peasant = PeasantState()
    peasant.get_mutator(storage.world).spawn(Field)


@version
def migrate_3(storage):
    for player in storage.all_players():
        player.send(
            "Game updated to version 3. Changes:\n"
            "* New locations: a town gate, a market square.\n"
            "* New NPC: a guard.\n"
            "* Cotton is now more rare")

    guard = GuardState()
    guard.get_mutator(storage.world).spawn(TownGate)


@version
def migrate_4(storage):
    for player in storage.all_players():
        player.send(
            "Game updated to version 4. News:\n"
            "• Wearables and crafting them\n"
            "• Barter with NPCs\n"
            "• Try to make it to market square!")

    for actor in storage.all_players():
        actor.wears = DirtyRags()

    for actor in storage.all_npcs():
        if isinstance(actor, PeasantState):
            actor.name = "Jack"
            actor.wears = RoughspunTunic()

        if isinstance(actor, GuardState):
            actor.name = "gate guard"
            actor.wears = Overcoat()

    if not storage.world[VillageHouse.id].means:
        storage.world[VillageHouse.id].means.add(Distaff())


def dry_send_callback_factory(chatkey):
    def callback(msg):
        print "%s\t%s" % (chatkey, msg)
    return callback


def migrate(dry_run=True):
    storage = Storage(dry_send_callback_factory if dry_run else bot.send_callback_factory)

    version = storage.version
    old_version = version

    if dry_run:
        print "No worries, it's a dry run"

    version = version or 0
    print "Current version is %d" % version
    while len(migrations) > version:
        print "Migrating storage from version %d to %d" % (version, version + 1)
        migrations[version](storage)
        version += 1

    storage.version = version
    if dry_run:
        storage.print_dump()
        storage.lock_object.release()
    else:
        storage.save()


if __name__ == '__main__':
    from sys import argv

    migrate(dry_run=not (len(argv) > 1 and argv[1] == "--run"))
