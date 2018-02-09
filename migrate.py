#!/usr/bin/env python

from mud.chatflow import Chatflow
from mud.locations import Field, TownGate
from mud.production import Land
from mud.npcs import PeasantState, GuardState

from bot import bot
from storage import Storage


def migrate_1(storage):
    for player in storage.all_players():
        player.send("Game updated to version 1. Sorry for killing everyone, guys")

        mutator = Chatflow(player, storage.world, bot.command_prefix)

        if player.name == 'Player':
            mutator.die()
            player.name = None
            mutator.process_message('%sstart' % bot.command_prefix)

    if not storage.world[Field.id].means:
        storage.world[Field.id].means.add(Land())


def migrate_2(storage):
    for player in storage.all_players():
        player.send("Game updated to version 2. Welcome a hungry and lazy peasant!")

    peasant = PeasantState()
    peasant.mutator_class(peasant, storage.world).spawn(Field)


def migrate_3(storage):
    for player in storage.all_players():
        player.send(
            "Game updated to version 3. Changes:\n"\
            "* New locations: a town gate, a market square.\n"
            "* New NPC: a guard.\n"
            "* Cotton is now more rare")

    peasant = GuardState()
    peasant.mutator_class(peasant, storage.world).spawn(TownGate)


migrations = [migrate_1, migrate_2, migrate_3]


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
