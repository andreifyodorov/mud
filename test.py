#!/usr/bin/env python

import unittest
import fnmatch
import re

from storage import Storage
from migrate import migrations
from mud.player import CommandPrefix
from mud.commodities import Vegetable, Mushroom, Cotton, Spindle, Shovel, DirtyRags, RoughspunTunic
from mud.npcs import PeasantState, RatState
from mud.locations import Direction, Field
from mud.attacks import Kick, Punch, Bash


class MockSendMessage(object):
    def __init__(self):
        self.reset()

    def send_callback_factory(self, chatkey):
        def callback(msg):
            # print(msg)
            self.messages.append(msg)
        return callback

    def reset(self):
        self.messages = list()

    def __iter__(self):
        return self

    def __next__(self):
        if not self.messages:
            raise StopIteration
        return self.messages.pop(0)

    def dump(self):
        print("\n".join(self.messages))


class MockLockObject(object):
    def acquire(self):
        pass

    def release(self):
        pass


class MockRedis(object):
    def __init__(self):
        self.dict = {}

    def get(self, key):
        return self.dict.get(key, None)

    def set(self, key, value):
        self.dict[key] = value

    def keys(self, pattern):
        regex = re.compile(fnmatch.translate(pattern))
        return [key for key in self.dict.keys() if regex.match(key)]

    def lock(self, *args, **kwargs):
        return MockLockObject()

    def delete(self, key):
        if key in self.dict:
            del self.dict[key]


class ChatflowTestCase(unittest.TestCase):
    @classmethod
    def get_storage(cls):
        return Storage(cls.messages.send_callback_factory, redis=cls.redis, cmd_pfx=cls.cmd_pfx)

    @classmethod
    def setUpClass(cls):
        cls.messages = MockSendMessage()
        cls.cmd_pfx = CommandPrefix('#')
        cls.redis = MockRedis()
        storage = cls.get_storage()
        for migrate in migrations:
            migrate(storage)
        storage.save()

    def setUp(self):
        self.storage = self.get_storage()
        self.world = self.storage.world
        self.player = self.storage.get_player_state(0)
        self.chatflow = self.player.get_mutator(self.world)

    def tearDown(self):
        self.messages.reset()
        self.storage.save()

    def assertReplyContains(self, *args):
        messages = "\n".join(self.messages)
        for pattern in args:
            self.assertRegex(messages, pattern)

    def send(self, cmd):
        # print(f"> {cmd}")
        self.chatflow.process_message(cmd)

    def cycle(self, loop, cond, error_message, max_cycles=100, debug=None):
        i = 0
        while i < max_cycles:
            loop()
            if callable(debug):
                print(debug())
            if cond():
                break
            i += 1
        else:
            raise AssertionError("%s in %d cycles" % (error_message, i))

    def get_option(self, match):
        option = None
        messages = "\n".join(self.messages)
        for line in messages.split("\n"):
            if match in line:
                option = line[:2]
        self.assertTrue(option is not None, f"Can't find '{match}' in '{messages}'")
        return option

    def test_01_start(self):
        self.send('#start')
        self.assertFalse(self.player.alive)

        self.send('Player')
        self.assertEqual(self.player.name, 'Player')
        self.assertReplyContains('#name', '#start')

        self.send('#name')
        self.send('Test Player')
        self.assertEqual(self.player.name, 'Test Player')

        self.send('#me')
        self.assertReplyContains('Test Player')

    def test_020_sleep(self):
        self.send('#start')

        self.cycle(
            self.chatflow.act,
            lambda: not self.player.recieves_announces,
            "Player didn't fall asleep")

        self.send("#where")
        self.assertTrue(self.player.recieves_announces)

        for _ in range(50):
            self.send("#where")
            self.chatflow.act()
        self.assertTrue(self.player.recieves_announces)

    def test_021_pick_drop_collect(self):
        self.send("#drop")
        self.assertReplyContains("already empty")

        self.send("#pick")
        self.assertReplyContains("nothing on the ground")

        self.send("#collect")
        self.assertReplyContains("nothing on the ground")

        veg = Vegetable()
        self.chatflow.location.items.add(veg)

        self.send("#pick")
        self.assertReplyContains("You put")
        self.assertTrue(veg in self.player.bag)

        self.send("#drop")
        self.send(self.get_option("vegetable"))
        self.assertReplyContains("You drop")

        self.chatflow.location.items.add(Mushroom())
        self.send("#pick")
        self.chatflow.location.items.clear()  # someone took everything
        self.send(self.get_option("vegetable"))
        self.assertReplyContains("nothing on the ground")

        self.chatflow.location.items.add(veg)
        self.chatflow.location.items.add(Mushroom())
        self.send("#pick")
        self.chatflow.location.items.remove(veg)  # someone took it
        self.send(self.get_option("vegetable"))
        self.assertReplyContains("You put nothing")
        self.chatflow.location.items.clear()
        self.player.bag.clear()

    def test_022_moving_around(self):
        self.send("#north")
        self.assertReplyContains("You are", "village")
        self.send("#south")
        self.assertReplyContains("You are", "field")

    def test_025_field(self):
        self.send("#where")
        self.assertReplyContains('#farm')

        self.send('#farm')
        self.assertReplyContains('#bag')
        self.assertEqual(len(self.player.bag), 1)

        self.send('#farm')
        self.assertReplyContains("can't farm now")
        self.assertEqual(self.player.cooldown["produce"], 0)

        self.chatflow.act()
        self.assertNotIn('produce', self.player.cooldown)

        self.send('#farm')

        self.assertReplyContains('#bag')
        self.assertEqual(len(self.player.bag), 2)
        self.send('#bag')

        self.player.bag.clear()
        self.player.bag.add(Vegetable())
        self.send('#bag')
        self.assertReplyContains('#eat', '#drop')

    def test_03_peasant_ai(self):
        peasant, = self.chatflow.location.actors.filter(PeasantState)
        mutator = peasant.get_mutator(self.world)

        self.assertTrue(mutator.go.is_available)
        self.assertCountEqual(mutator.go.get_args(), Direction.compass)

        self.send('#drop')
        self.send(self.get_option("vegetable"))

        self.cycle(
            self.world.enact,
            lambda: any(peasant.bag.filter(Vegetable)),
            "Peasant didn't pick a vegetable up")

        self.cycle(
            self.world.enact,
            lambda: not any(peasant.bag.filter(Vegetable)),
            "Peasant didn't eat a vegetable")

        self.send('#north')
        self.send('#enter')

        self.cycle(
            lambda: mutator.deteriorate(peasant.wears),
            lambda: isinstance(peasant.wears, DirtyRags),
            "Peasant's tunic did not deteriorate")

        self.cycle(
            self.world.enact,
            lambda: peasant.location == self.player.location,
            "Peasant didn't return to the house")

        self.cycle(
            self.world.enact,
            lambda: any(peasant.bag.filter(Spindle)),
            "Peasant didn't make a spindle")

        peasant.bag.update([Cotton(), Cotton()])
        self.cycle(
            self.world.enact,
            lambda: isinstance(peasant.wears, RoughspunTunic),
            "Peasant didn't spin a tunic",
            max_cycles=200)

        self.assertEqual(next(peasant.bag.filter(Spindle)).usages, 1)

        self.send('#exit')
        self.send('#south')
        self.assertIs(Field, self.player.location)

        self.cycle(
            self.world.enact,
            lambda: peasant.location == self.player.location,
            "Peasant didn't return to a field")

    def test_04_barter(self):
        peasant, = self.chatflow.location.actors.filter(PeasantState)
        self.player.bag.add(Vegetable())
        self.send('#barter')
        self.send(self.get_option('spindle'))
        self.assertReplyContains('#1')
        self.send('#1')
        self.assertReplyContains('spindle')
        self.send('#bag')
        self.assertReplyContains('spindle')

    def test_05_guard(self):
        self.send('#north')
        self.assertReplyContains('village', '#north')
        self.send('#north')
        self.assertReplyContains('gate', '#north')
        loc = self.player.location
        self.send('#north')
        self.assertIs(loc, self.player.location)  # guard blocks the way

    def test_06_tunic(self):
        spindle = next(self.player.bag.filter(Spindle))
        self.send('#south')

        self.assertReplyContains('village', '#enter')
        self.send('#enter')
        self.assertReplyContains('#spin')

        self.send('#spin')
        self.assertReplyContains('2 balls of cotton')

        self.player.bag.update((Cotton(), Cotton()))
        self.send('#spin')
        self.assertReplyContains('tunic', '#bag')
        self.assertEqual(spindle.usages, 2)

        self.send('#me')
        self.assertReplyContains('falling apart spindle')  # tool wear out
        self.assertIs(self.player.wields, spindle)
        self.assertFalse(spindle in self.player.bag)

        self.send('#wear')
        self.assertReplyContains('tunic')

        self.chatflow.act()

        self.player.bag.update((Cotton(), Cotton()))
        self.send('#spin')
        self.assertReplyContains('disintegrates', 'tunic')
        self.assertEqual(spindle.usages, 3)
        self.assertIsNone(self.player.wields)

        self.send('#exit')
        self.assertReplyContains('village', '#north')

    def test_07_merchant(self):
        self.send('#north')
        self.send('#north')
        old_bag_len = len(self.player.bag)
        self.assertReplyContains('merchant')
        self.send('#sell')
        self.assertReplyContains('#1')
        self.send('#1')
        self.assertTrue(old_bag_len > len(self.player.bag))
        self.assertTrue(self.player.credits > 0)
        self.send('#buy')
        self.assertReplyContains('#1')
        self.send('#1')
        self.assertTrue(old_bag_len == len(self.player.bag))
        self.assertTrue(self.player.credits == 0)

    def test_08_shovel(self):
        self.send('#west')
        self.send('#enter')

        self.chatflow.act()
        self.send('#make')
        self.assertReplyContains('shovel')
        shovel = next(self.player.bag.filter(Shovel))

        self.send('#exit')
        self.send('#east')
        self.send('#south')
        self.send('#south')
        self.send('#south')

        for n in range(5):
            if n:
                self.assertIs(self.player.wields, shovel)
                self.assertNotIn(shovel, self.player.bag, msg=n)
            self.chatflow.act()
            self.send('#farm')
        self.assertIs(self.player.wields, None)
        self.assertNotIn(shovel, self.player.bag)

    def test_09_mushroom(self):
        self.cycle(
            lambda: self.send('#south'),
            lambda: "mushroom" in "\n".join(self.messages),
            "Couldn't find a mushroom",
            max_cycles=200)

        self.send('#pick')
        self.assertReplyContains('mushroom')
        self.assertTrue(any(self.player.bag.filter(Mushroom)))
        self.send('#eat')

        self.send(self.get_option('mushroom'))
        self.assertReplyContains('high')
        self.assertTrue(self.player.is_high)

        self.cycle(
            self.chatflow.act,
            lambda: not self.player.is_high,
            "Player didn't sober up")

    def test_10_rat(self):
        self.chatflow._relocate_self(Field)
        rat, = self.chatflow.location.actors.filter(RatState)
        self.assertGreater(rat.hitpoints, 0)

        self.send("#attack")
        self.send(self.get_option("rat"))

        self.assertIs(self.player.victim, rat)

        had_hitpoints = rat.hitpoints
        self.send(f"#{Kick}")
        self.assertLess(rat.hitpoints, had_hitpoints)
        self.assertTrue(self.chatflow.coolsdown(Kick.verb))

        had_hitpoints = rat.hitpoints
        self.send(f"#{Kick}")
        self.assertEqual(rat.hitpoints, had_hitpoints)

        self.send("#unequip")
        self.send(f"#{Bash}")
        self.assertEqual(rat.hitpoints, had_hitpoints)

        self.send(f"#{Punch}")
        self.assertLess(rat.hitpoints, had_hitpoints)

        # escaping a location shouldn't prevent npc from kicking you during the same cycle
        self.send("#south")

        had_hitpoints = self.player.hitpoints
        self.world.enact()
        self.assertReplyContains('rat bites you')
        # self.assertLess(self.player.hitpoints, had_hitpoints)

        self.assertIsNone(self.player.victim)
        self.assertIsNone(rat.victim)

        self.send("#north")
        self.send("#attack")
        self.send(self.get_option("rat"))

        self.send(f"#{Punch}")
        self.world.enact()
        self.assertReplyContains('rat dies')

        self.assertIsNone(self.player.victim)
        self.cycle(
            self.world.enact,
            lambda: any(self.chatflow.location.actors.filter(RatState)),
            "Rat didn't respawn")

    def test_11_coop_attack(self):
        player2 = self.storage.get_player_state(1)
        chatflow2 = player2.get_mutator(self.world)

        chatflow2.process_message("#start")
        chatflow2.process_message("Player2")
        chatflow2.process_message("#start")

        self.assertIn(player2, self.chatflow.location.actors)
        chatflow2.process_message("#attack")
        chatflow2.process_message(self.get_option("rat"))
        rat, = self.chatflow.location.actors.filter(RatState)

        self.assertIs(player2.victim, rat)
        self.assertIs(rat.victim, player2)

        self.assertIs(self.player.location, Field)
        self.send("#attack")
        self.send(self.get_option("rat"))

        self.assertIs(self.player.victim, rat)
        self.assertIs(rat.victim, player2)

        chatflow2.process_message("#north")
        self.world.enact()

        self.assertIsNone(player2.victim)
        self.assertIs(self.player.victim, rat)
        self.assertIs(rat.victim, self.player)

        self.send("#north")
        self.world.enact()
        self.assertIsNone(self.player.victim)
        self.assertIsNone(rat.victim)


def load_tests(loader, tests, pattern):
    suite = unittest.TestLoader().loadTestsFromTestCase(ChatflowTestCase)
    return suite


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
