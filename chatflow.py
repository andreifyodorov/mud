#!/usr/bin/env python

# - add items
# - add inventory
# - add npcs
# - add (re)start sequence
# - autocomplete commands /n instead of /north

from locations import StartLocation
from itertools import count


class Actor(object):
    def __init__(self, _id):
        self.id = _id
        self.alive = False
        self.location = None
        self.inventory = {}


class Player(Actor):
    def __init__(self, _id):
        super(Player, self,).__init__(_id)
        self.confirm = {}


class UnknownStateMutatorCommand(Exception):
    pass


class StateMutator(object):
    def __init__(self, actor, world):
        self.actor = actor
        self.world = world

    @property
    def location(self):
        return self.world[self.location.id]

    def get_commands(self):
        for l in self.actor.location.exits.keys():
            yield l, lambda: self.go(l)

    def dispatch(self, command, *args):
        for cmd, handler in self.get_commands():
            if cmd == command:
                return handler(*args)
        raise UnknownStateMutatorCommand

    def go(self, direction):
        self.actor.location = self.actor.location.exits[direction]['location']


class Chatflow(StateMutator):
    def __init__(self, actor, world, reply_callback, command_prefix=""):
        super(Chatflow, self).__init__(actor, world)
        self.reply_callback = reply_callback
        self.command_prefix = command_prefix


    def process_message(self, text):
        for tokens in self.tokenize(text):
            for command, args in self.get_user_commands(*tokens):
                try:
                    result = self.dispatch(command, *args)
                    self.reply(result)
                except UnknownStateMutatorCommand:
                    self.reply(
                        "Unknown command. Send %shelp for list of commands" % self.command_prefix)


    def tokenize(self, text):
        yield text.lower().split(" ")  # tokenize


    def get_user_commands(self, command, *args):
        if self.command_prefix and not command.startswith(self.command_prefix):
            return
        yield command[len(self.command_prefix):], args
        # additional state mutation loop
        if 'yes' in self.actor.confirm:
            yield self.actor.confirm['command'], []


    def confirmation(self, command, question, f):
        def handler():
            if 'yes' in self.actor.confirm:
                self.actor.confirm.clear()
                return f()
            else:
                self.actor.confirm.update(command=command)
                return "{0} Send {1}yes or {1}no".format(question, self.command_prefix)
        return command, handler


    def get_commands(self):
        yield 'help', self.help

        if self.actor.alive:

            if self.actor.confirm and not 'answered' in self.actor.confirm:
                yield 'yes', lambda: self.actor.confirm.update(answered=True, yes=True)
                yield 'no', lambda: self.actor.confirm.clear()

            else:
                yield self.confirmation(
                    'restart', "Do you want to restart the game?", self.start)

                yield 'where', lambda: self.where(verb="are still")

                for command in super(Chatflow, self).get_commands():
                    yield command

        else:
            yield 'start', self.start


    def reply(self, result):
        if isinstance(result, basestring):
            self.reply_callback(result)
        elif result is not None:
            self.reply_callback("\n".join(result))


    def start(self):
        self.actor.alive = True
        self.actor.location = StartLocation
        return self.where(verb="wake up")


    def help(self):
        commands_list = (self.command_prefix + cmd for cmd, hndlr in self.get_commands())
        return "Known commands are: %s" % ", ".join(commands_list)


    def where(self, verb="are"):
        yield 'You %s %s' % (verb, self.actor.location.descr)
        for direction, exit in self.actor.location.exits.iteritems():
            yield exit['descr'] % (self.command_prefix + direction)


    def go(self, direction):
        super(Chatflow, self).go(direction)
        return self.where()


if __name__ == '__main__':
    from colored import fore, style
    import re

    def output(msg):
        msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
        print fore.YELLOW + msg + style.RESET

    player = Player(1)
    world = {}

    s = '/start'
    while True:
        chatflow = Chatflow(player, world, output, command_prefix='/')
        chatflow.process_message(s)

        try:
            # s = raw_input('%s> ' % ' '.join('/' + c for c, h in chatflow.get_commands()))
            s = raw_input('%s> ' % player.confirm)
        except (EOFError, KeyboardInterrupt):
            break

