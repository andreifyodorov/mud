#!/usr/bin/env python

from pprint import pprint

from mud.player import Chatflow
from mud.locations import Field, TownGate, VillageHouse, MarketSquare, Factory
from mud.production import Land, Distaff, Workbench
from mud.npcs import PeasantState, GuardState, MerchantState
from mud.commodities import DirtyRags, RoughspunTunic, Overcoat

from bot import bot
from storage import Storage

from deepdiff import DeepDiff


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
            "• New locations: a town gate, a market square.\n"
            "• New NPC: a guard.\n"
            "• Cotton is now more rare")

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

    for actor in storage.world.actors():
        if isinstance(actor, PeasantState):
            actor.name = "Jack"
            actor.wears = RoughspunTunic()

        if isinstance(actor, GuardState):
            actor.name = "gate guard"
            actor.wears = Overcoat()

    if not storage.world[VillageHouse.id].means:
        storage.world[VillageHouse.id].means.add(Distaff())


@version
def migrate_5(storage):
    for player in storage.all_players():
        player.send("Game updated to version 5. Added a merchant.")

    for actor in storage.world.actors():
        if isinstance(actor, GuardState):
            actor.name = "a gate guard"

    merchant = MerchantState()
    merchant.get_mutator(storage.world).spawn(MarketSquare)


@version
def migrate_6(storage):
    for player in storage.all_players():
        player.send(
            "Game updated to version 6. News:\n"
            "• Factory district\n"
            "• Shovel production to foster agriculture\n"
            "• Tools wear out")

    guard = GuardState()
    guard.get_mutator(storage.world).spawn(MarketSquare)

    if not storage.world[Factory.id].means:
        storage.world[Factory.id].means.add(Workbench())


@version
def migrate_7(storage):
    for player in storage.all_players():
        if hasattr(player, "last_command_time") and player.last_command_time is None:
            player.last_command_time = storage.world.time


@version
def migrate_8(storage):
    for player in storage.all_players():
        time = storage.world.time

        if hasattr(player, "last_command_time"):
            last_time = player.last_command_time
            distance = 20 if not last_time else 20 - time + last_time
            if 0 < distance <= 20:
                player.counters["active"] = distance - 1
            player.last_command_time = None

        if hasattr(player, "last_success_time"):
            last_time = player.last_success_time
            if player.last_success_time == time:
                player.counters["cooldown"] = 0
            player.last_success_time = None


@version
def migrate_9(storage):
    for player in storage.all_players():
        if "active" in player.counters:
            player.cooldown["active"] = player.counters["active"]
        if "cooldown" in player.counters:
            player.cooldown["produce"] = player.counters["cooldown"]
        del player.counters

    for actor in storage.world.actors():
        if isinstance(actor, PeasantState):
            for key in ("tired", "hungry"):
                if key in actor.counters:
                    actor.cooldown[key] = actor.counters[key]
                    del actor.counters[key]


# @version
# def migrate_10(storage):
#     for actor in storage.world.actors():
#         if actor.max_hitpoints and actor.alive:
#             actor.hitpoints = actor.max_hitpoints


def dry_send_callback_factory(chatkey):
    def callback(msg):
        print(chatkey, msg, sep="\t")
    return callback


def migrate(dry_run=True):
    storage = Storage(dry_send_callback_factory if dry_run else bot.send_callback_factory, bot.cmd_pfx)

    version = storage.version

    if dry_run:
        print("No worries, it's a dry run")
        current_dump = dict(storage.dump())

    version = version or 0
    print(f"Current version is {version}")
    while len(migrations) > version:
        print(f"Migrating storage from version {version:d} to {version + 1:d}")
        migrations[version](storage)
        version += 1

    storage.version = version
    if dry_run:
        storage.print_dump()
        print()
        print("Difference:")
        pprint(DeepDiff(current_dump, dict(storage.dump()), verbose_level=2))
        storage.lock_object.release()
    else:
        storage.save()
        bot.send_messages()


if __name__ == '__main__':
    from sys import argv

    migrate(dry_run=not (len(argv) > 1 and argv[1] == "--run"))
