#!/usr/bin/env python

import unittest
import fnmatch
import re

from storage import Storage
from migrate import migrations
from mud.chatflow import Chatflow, CommandPrefix
from mud.states import PlayerState
from mud.commodities import Vegetable, Cotton, Spindle, Shovel
from mud.npcs import PeasantState


class MockSendMessage(object):
    def __init__(self):
        self.reset()

    def send_callback_factory(self, chatkey):
        def callback(msg):
            self.messages.append(msg)
        return callback

    def reset(self):
        self.messages = list()

    def __iter__(self):
        return self

    def next(self):
        if not self.messages:
            raise StopIteration
        return self.messages.pop(0)


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


class ChatflowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.messages = MockSendMessage()
        cls.storage = Storage(cls.messages.send_callback_factory, redis=MockRedis())

        for migrate in migrations:
            migrate(cls.storage)

        cls.player = PlayerState(send_callback=cls.messages.send_callback_factory(0))
        cls.chatflow = Chatflow(cls.player, cls.storage.world, cmd_pfx=CommandPrefix('/'))


    def setUp(self):
        self.messages.reset()

    def assertReplyContains(self, *args):
        messages = "\n".join(self.messages)
        for pattern in args:
            self.assertRegexpMatches(messages, pattern)

    def send(self, cmd):
        self.chatflow.process_message(cmd)

    def test_01_start(self):
        self.send('/start')
        self.assertFalse(self.player.alive)

        self.send('Player')
        self.assertEqual(self.player.name, 'Player')
        self.assertReplyContains('/name', '/start')

        self.send('/name')
        self.send('Test Player')
        self.assertEqual(self.player.name, 'Test Player')

        self.send('/me')
        self.assertReplyContains('Test Player')


    def test_02_field(self):
        self.send('/start')
        self.assertReplyContains('/farm')

        self.send('/farm')
        self.assertReplyContains('/bag')
        self.assertEqual(len(self.player.bag), 1)

        self.player.bag.clear()
        self.player.bag.add(Vegetable())
        self.send('/bag')
        self.assertReplyContains('/eat', '/drop')


    def test_03_peasant_ai(self):
        peasant, = self.chatflow.location.actors.filter(PeasantState)
        i = 0
        while i < 100:
            self.storage.world.enact()
            if (any(peasant.bag.filter(Spindle))
                    and peasant.location == self.player.location):
                break
            i += 1
        else:
            raise AssertionError("Peasant didn't make a spindle in %d cycles" % i)

    def test_04_barter(self):
        self.send('/barter')
        self.assertReplyContains('/1', 'spindle')
        self.send('/1')
        self.assertReplyContains('/1')
        self.send('/1')
        self.assertReplyContains('spindle')
        self.send('/bag')
        self.assertReplyContains('spindle')

    def test_05_guard(self):
        self.send('/north')
        self.assertReplyContains('village', '/north')
        self.send('/north')
        self.assertReplyContains('gate', '/north')
        l = self.player.location
        self.send('/north')
        self.assertIs(l, self.player.location)  # guard blocks the way


    def test_06_tunic(self):
        spindle = next(self.player.bag.filter(Spindle))
        self.send('/south')

        self.assertReplyContains('village', '/enter')
        self.send('/enter')
        self.assertReplyContains('/spin')

        self.player.bag.update((Cotton(), Cotton()))
        self.send('/spin')
        self.assertReplyContains('tunic', '/bag')
        self.assertEqual(spindle.usages, 1)

        self.send('/me')
        self.assertReplyContains('used', 'spindle')  # tool wear out
        self.assertIs(self.player.wields, spindle)
        self.assertFalse(spindle in self.player.bag)

        self.send('/wear')
        self.assertReplyContains('tunic')

        self.storage.world.time += 1
        self.player.bag.update((Cotton(), Cotton()))
        self.send('/spin')
        self.assertReplyContains('tunic')
        self.assertEqual(spindle.usages, 2)

        self.storage.world.time += 1
        self.player.bag.update((Cotton(), Cotton()))
        self.send('/spin')
        self.assertReplyContains('disintegrates', 'tunic')
        self.assertEqual(spindle.usages, 3)
        self.assertIsNone(self.player.wields)

        self.send('/exit')
        self.assertReplyContains('village', '/north')


    def test_07_merchant(self):
        self.send('/north')
        self.send('/north')
        self.assertReplyContains('merchant')
        self.send('/sell')
        self.assertReplyContains('/1')
        self.send('/1')
        self.assertTrue(self.player.credits > 0)


    def test_08_shovel(self):
        self.send('/west')
        self.send('/north')

        self.storage.world.time += 1
        self.send('/make')
        self.assertReplyContains('shovel')
        shovel = next(self.player.bag.filter(Shovel))

        self.send('/exit')
        self.send('/east')
        self.send('/south')
        self.send('/south')
        self.send('/south')

        for n in range(5):
            self.storage.world.time += 1
            self.send('/farm')
            self.assertIs(self.player.wields, shovel if n < 4 else None)
            self.assertFalse(shovel in self.player.bag)



def load_tests(loader, tests, pattern):
    suite = unittest.TestLoader().loadTestsFromTestCase(ChatflowTestCase)
    return suite


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
