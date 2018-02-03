#!/usr/bin/env python

from bot import bot
from storage import Storage
from chatflow import Chatflow
from locations import Field
from production import Land


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


migrations = [migrate_1]


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
    while len(migrations) > version:
        print "Migrating storage from version %d to %d" % (version, version + 1)
        migrations[version](storage)
        version += 1

    if dry_run:
        storage.print_dump()
        storage.lock_object.release()
    else:
        storage.version = version
        storage.save()


if __name__ == '__main__':
    from sys import argv

    migrate(dry_run=not (len(argv) > 1 and argv[1] == "--run"))
