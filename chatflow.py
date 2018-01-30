#!/usr/bin/env python

# - add items
# - add bag
# - add npcs
# - add (re)start sequence
# - autocomplete commands /n instead of /north

from locations import StartLocation
from commodities import Vegetable
from itertools import chain


class State(object):
    pass


class ActorState(State):
    def __init__(self):
        super(ActorState, self).__init__()
        self.alive = False
        self.location = None
        self.bag = set()


class PlayerState(ActorState):

    def __init__(self, send_callback):
        super(PlayerState, self).__init__()
        self.send = send_callback or (lambda message: None)
        self.confirm = {}
        self.input = {}
        self.name = None

    @property
    def descr(self):
        return 'player called %s' % self.name


class WorldState(State):
    def __init__(self):
        super(WorldState, self).__init__()
        self.items = set()
        self.actors = set()

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors:
            if skip_sender is not None and actor is skip_sender:
                continue
            if isinstance(actor, PlayerState):
                actor.send(message.capitalize())


class UnknownStateMutatorCommand(Exception):
    pass


class StateMutator(object):
    def __init__(self, actor, world):
        self.actor = actor
        self.world = world

    @property
    def location(self):
        return self.world[self.actor.location.id]

    def anounce(self, message):
        self.location.broadcast("%s %s" % (self.actor.name, message), skip_sender=self.actor)

    def get_commands(self):
        for l in self.actor.location.exits.keys():
            yield l, lambda: self.go(l)
        if self.location.items:
            yield 'pick', self.pick
        if self.actor.bag:
            yield 'drop', self.drop

    def dispatch(self, command, *args, **kwargs):
        for cmd, handler in self.get_commands():
            if cmd == command:
                return handler(*args, **kwargs)
        raise UnknownStateMutatorCommand

    def die(self):
        if self.actor.alive:
            self.anounce('dies.')
            self.location.actors.remove(self.actor)
            self.location.items.update(self.actor.bag)
            self.actor.bag.clear()
            self.actor.alive = False

    def go(self, direction):
        old = self.actor.location
        new = self.actor.location.exits[direction]['location']
        self.anounce('leaves to %s.' % new.name)
        self.location.actors.remove(self.actor)
        self.actor.location = new
        self.anounce('arrives from %s.' % old.name)
        self.location.actors.add(self.actor)

    def pick(self):
        for item in self.location.items:
            self.anounce('picks up %s.' % item.name)
        self.actor.bag.update(self.location.items)
        self.location.items.clear()

    def drop(self):
        for item in self.actor.bag:
            self.anounce('drops %s on the ground.' % item.name)
        self.location.items.update(self.actor.bag)
        self.actor.bag.clear()


class Chatflow(StateMutator):
    def __init__(self, actor, world, command_prefix=""):
        super(Chatflow, self).__init__(actor, world)
        self.command_prefix = command_prefix


    def process_message(self, text):
        tokens = self.tokenize(text)
        if tokens:
            if self.actor.input:
                self.actor.input.update(answered=text)

            for command, args in self.get_command_args(*tokens):
                try:
                    result = self.dispatch(command, *args)
                    self.reply(result)
                except UnknownStateMutatorCommand:
                    if not 'answered' in self.actor.input:
                        self.reply("Unknown command. Send %shelp for list of commands"
                                   % self.command_prefix)
                else:
                    if 'answered' in self.actor.input:
                        self.actor.input.clear()


    def tokenize(self, text):
        return text.split(None, 1)


    def get_command_args(self, command, *args):
        if not self.command_prefix or command.startswith(self.command_prefix):
            yield command[len(self.command_prefix):].lower(), args

        # additional state mutation iterations

        if 'answered' in self.actor.input:
            yield self.actor.input['command'], [self.actor.input['answered']]

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
                yield self.confirmation('restart', "Do you want to restart the game?", self.die)

                yield 'where', lambda: self.where(verb="are still")

                if self.actor.bag:
                    yield 'bag', self.bag

                for command in super(Chatflow, self).get_commands():
                    yield command

        else:
            yield 'start', self.start
            yield 'name', self.name


    def reply(self, result):
        if isinstance(result, basestring):
            self.actor.send(result)
        elif result is not None:
            self.actor.send("\n".join(result))


    def welcome(self):
        yield "Hello and welcome to this little MUD game."


    def name(self, name=None):
        if name is None:
            yield "Please tell me your name."
            self.actor.input.update(command='name')

        else:
            yield "Hello, %s." % name
            yield "You can {0}start the game now " \
                  "or give me another {0}name.".format(self.command_prefix)
            self.actor.name = name


    def start(self):
        if self.actor.name is None:
            return chain(self.welcome(), self.name())
        self.actor.alive = True
        self.actor.location = StartLocation
        self.anounce('materializes.')
        self.location.actors.add(self.actor)
        return self.where(verb="wake up")


    def help(self):
        commands_list = (self.command_prefix + cmd for cmd, hndlr in self.get_commands())
        return "Known commands are: %s" % ", ".join(commands_list)


    def where(self, verb="are"):
        yield 'You %s %s' % (verb, self.actor.location.descr)
        for direction, exit in self.actor.location.exits.iteritems():
            yield exit['descr'] % (self.command_prefix + direction)
        for item in self.location.items:
            yield "On the ground you see %s. You can %spick it up." % (item.name, self.command_prefix)
        for actor in self.location.actors:
            if actor is self.actor:
                continue
            yield "You see %s." % actor.descr


    def go(self, direction):
        super(Chatflow, self).go(direction)
        return self.where()


    def pick(self):
        for item in self.location.items:
            yield "You put %s into your %sbag." % (item.name, self.command_prefix)
        super(Chatflow, self).pick()


    def drop(self):
        for item in self.actor.bag:
            yield "You drop %s on the ground." % item.name
        super(Chatflow, self).drop()


    def bag(self):
        if len(self.actor.bag) == 1:
            item, = self.actor.bag
            yield "In your bag there's nothing but %s. You can %sdrop it" \
                  % (item.name, self.command_prefix)
        else:
            yield "You look into your bag and see:"
            for n, item in enumerate(self.actor.bag.values()):
                yield "%d. %s" % (n + 1, item.name)
            yield "You can %sdrop it" % (self.command_prefix)


    def die(self):
        super(Chatflow, self).die()
        return "You die."



if __name__ == '__main__':
    from colored import fore, style
    import re
    from collections import defaultdict

    def output(msg):
        msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
        print fore.YELLOW + msg + style.RESET

    player = PlayerState(send_callback=output)

    world = defaultdict(WorldState)
    world[StartLocation.id].items.add(Vegetable())

    s = '/start'
    while True:
        chatflow = Chatflow(player, world, command_prefix='/')
        chatflow.process_message(s)

        try:
            # s = raw_input('%s> ' % ' '.join('/' + c for c, h in chatflow.get_commands()))
            s = raw_input('%s> ' % player.input)
        except (EOFError, KeyboardInterrupt):
            break


