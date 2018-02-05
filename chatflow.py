#!/usr/bin/env python

from locations import StartLocation
from commodities import Vegetable, Cotton
from production import Land
from itertools import chain


class State(object):
    pass


class ActorState(State):
    def __init__(self):
        super(ActorState, self).__init__()
        self.alive = False
        self.location = None
        self.bag = set()
        self.coins = 0


class PlayerState(ActorState):

    def __init__(self, send_callback):
        super(PlayerState, self).__init__()
        self.send = send_callback or (lambda message: None)
        self.confirm = {}
        self.input = {}
        self.name = None

    @property
    def descr(self):
        return '%s (player)' % self.name


class WorldState(State):
    def __init__(self):
        super(WorldState, self).__init__()
        self.items = set()
        self.actors = set()
        self.means = set()

    def broadcast(self, message, skip_sender=None):
        for actor in self.actors:
            if skip_sender is not None and actor is skip_sender:
                continue
            if isinstance(actor, PlayerState):
                actor.send(message.capitalize())


def pretty_list(items):
    items = sorted(items, key=lambda item: item.name)
    if len(items) == 0:
        return 'nothing'
    if len(items) == 1:
        item, = items
        return item.name
    return "%s and %s" % (', '.join(i.name for i in items[:-1]), items[-1].name)


class StateMutator(object):
    def __init__(self, actor, world):
        self.actor = actor
        self.world = world

    @property
    def location(self):
        return self.world[self.actor.location.id]

    def anounce(self, message):
        self.location.broadcast("%s %s" % (self.actor.name, message), skip_sender=self.actor)

    def spawn(self, location):
        if not self.actor.location and not self.actor.alive:
            self.actor.alive = True
            self.actor.location = location
            self.location.actors.add(self.actor)
            self.anounce('materializes.')

    def die(self):
        if self.actor.alive:
            self.anounce('dies.')
            self.location.actors.remove(self.actor)
            self.location.items.update(self.actor.bag)
            self.actor.bag.clear()
            self.actor.location = None
            self.actor.alive = False

    def go(self, direction):
        old = self.actor.location
        new = self.actor.location.exits[direction]['location']
        self.anounce('leaves to %s.' % new.name)
        self.location.actors.remove(self.actor)
        self.actor.location = new
        self.anounce('arrives from %s.' % old.name)
        self.location.actors.add(self.actor)

    def _relocate(self, item_or_items, source, destination=None):
        items = set()
        try:
            items.update(item_or_items)
        except TypeError:
            items.add(item_or_items)
        items = items & source
        if items:
            if destination is not None:
                destination.update(items)
            source.difference_update(items)
        return items

    def pick(self, item_or_items):
        items = self._relocate(item_or_items, self.location.items, self.actor.bag)
        if items:
            self.anounce('picks up %s.' % pretty_list(items))
        return items

    def drop(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag, self.location.items)
        if items:
            self.anounce('drops %s on the ground.' % pretty_list(items))
        return items

    def eat(self, item_or_items):
        items = self._relocate(item_or_items, self.actor.bag)
        if items:
            self.anounce('eats %s.' % pretty_list(items))
        return items

    def produce(self, means):
        fruit = means.produce()
        self.anounce('%ss %s.' % (means.verb, fruit.name))
        self.actor.bag.add(fruit)
        return fruit


class Npc(ActorState):
    mutator_class = StateMutator


class PeasantMutator(StateMutator):
    def act(self):
        edibles = (item for item in self.location.items if isinstance(item, Vegetable))
        if self.pick(edibles):
            return  # end cycle

        edibles = (item for item in self.actor.bag if isinstance(item, Vegetable))
        self.eat(edibles)


class PeasantState(Npc):
    mutator_class = PeasantMutator
    name = 'a peasant'
    descr = 'a hungry and lazy peasant'


class UnknownChatflowCommand(Exception):
    pass


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
                except UnknownChatflowCommand:
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


    def choice(self, command, f, bag, all_=False):
        bag = sorted(bag, key=lambda item: item.name)

        def prompt():
            all_msg = " or %s %sall" % (command, self.command_prefix) if all_ else str()
            yield "Please choose what to %s%s:" % (command, all_msg)
            for n, item in enumerate(bag):
                yield "%s%d. %s" % (self.command_prefix, n + 1, item.name)
            self.actor.input.clear()
            self.actor.input.update(command=command)

        def handler(arg=None):
            item = None

            if self.command_prefix and arg and arg.startswith(self.command_prefix):
                arg = arg[len(self.command_prefix):]

            if arg and arg.lower() == 'all':
                return f(bag)

            if len(bag) == 1:
                item, = bag
            elif isinstance(arg, basestring) and arg.isdigit() and arg != '0':
                try:
                    item = bag[int(arg) - 1]
                except:
                    pass

            if not item:
                return prompt()
            else:
                return f(item)

        return command, handler


    def confirmation(self, command, f, question):
        def handler():
            if 'yes' in self.actor.confirm:
                self.actor.confirm.clear()
                return f()
            else:
                self.actor.confirm.update(command=command)
                return "{0} Send {1}yes or {1}no".format(question, self.command_prefix)
        return command, handler


    def dispatch(self, command, *args, **kwargs):
        for cmd, handler in self.get_commands():
            if cmd == command:
                return handler(*args, **kwargs)
        raise UnknownChatflowCommand


    def get_commands(self):
        yield 'help', self.help

        if self.actor.confirm and not 'answered' in self.actor.confirm:
            yield 'yes', lambda: self.actor.confirm.update(answered=True, yes=True)
            yield 'no', lambda: self.actor.confirm.clear()
            return

        if self.actor.alive:
            yield self.confirmation('restart', self.die, "Do you want to restart the game?")

            yield 'where', lambda: self.where(verb="are still")

            for means in self.location.means:
                yield means.verb, lambda: self.produce(means)

            for l in self.actor.location.exits.keys():
                yield l, lambda: self.go(l)

            if self.location.items:
                yield self.choice('pick', self.pick, self.location.items, all_=True)
                if len(self.location.items) > 1:
                    yield 'collect', lambda: self.pick(self.location.items)

            if self.actor.bag:
                yield 'bag', self.bag
                yield self.choice('drop', self.drop, self.actor.bag, all_=True)

                edibles = set(item for item in self.actor.bag if isinstance(item, Vegetable))
                if edibles:
                    yield self.choice('eat', self.eat, edibles)
            else:
                if self.actor.coins:
                    yield 'bag', lambda: 'Your bag is empty. You have %d coins.' % self.actor.coins
                else:
                    yield 'bag', lambda: 'Your bag is empty and you have no coins.'

            return

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
        self.spawn(StartLocation)
        return self.where(verb="wake up")


    def help(self):
        commands_list = (self.command_prefix + cmd for cmd, hndlr in self.get_commands())
        return "Known commands are: %s" % ", ".join(commands_list)


    def where(self, verb="are"):
        yield 'You %s %s' % (verb, self.actor.location.descr)

        for means in self.location.means:
            yield means.descr % (self.command_prefix + means.verb)

        for direction, exit in self.actor.location.exits.iteritems():
            yield exit['descr'] % (self.command_prefix + direction)

        if len(self.location.items) == 1:
            for item in self.location.items:
                yield "On the ground you see %s. You can %spick it up." \
                      % (item.name, self.command_prefix)
        elif len(self.location.items) > 1:
            yield "On the ground you see {items}. You can {0}pick or {0}collect them all." \
                  .format(self.command_prefix, items=pretty_list(self.location.items))

        for actor in self.location.actors:
            if actor is self.actor:
                continue
            yield "You see %s." % actor.descr


    def go(self, direction):
        super(Chatflow, self).go(direction)
        return self.where()


    def pick(self, item_or_items):
        items = super(Chatflow, self).pick(item_or_items)
        yield "You put %s into your %sbag." % (pretty_list(items), self.command_prefix)


    def drop(self, item_or_items):
        items = super(Chatflow, self).drop(item_or_items)
        yield "You drop %s on the ground." % pretty_list(items)


    def eat(self, item_or_items):
        items = super(Chatflow, self).eat(item_or_items)
        yield "You eat %s." % pretty_list(items)


    def bag(self):
        coins_message = None
        if self.actor.coins:
            coins_message = "You have %d coins." % self.actor.coins
        else:
            coins_message = "You have no coins."

        if len(self.actor.bag) == 1:
            item, = self.actor.bag
            yield "In your bag there's nothing but %s. You can %sdrop it." \
                  % (item.name, self.command_prefix)
            yield coins_message
        else:
            yield "You look into your bag and see:"
            seen_veggies = False
            for n, item in enumerate(sorted(self.actor.bag, key=lambda item: item.name)):
                item_str = "%d. %s" % (n + 1, item.name)
                if isinstance(item, Vegetable) and not seen_veggies:
                    item_str += ", you can %seat it" % self.command_prefix
                    seen_veggies = True
                yield item_str
            yield coins_message
            yield "You can %sdrop [number]." % self.command_prefix


    def die(self):
        super(Chatflow, self).die()
        return "You die."


    def produce(self, means):
        fruit = super(Chatflow, self).produce(means)
        return "You %s %s. You put it into a %sbag." % (means.verb, fruit.name, self.command_prefix)


if __name__ == '__main__':
    from colored import fore, style
    import re
    from collections import defaultdict

    def output(msg):
        msg = re.sub('\/\w+', lambda m: fore.CYAN + m.group(0) + fore.YELLOW, msg)
        print fore.YELLOW + msg + style.RESET

    def observe(msg):
        print fore.BLUE + msg + style.RESET

    world = defaultdict(WorldState)
    world[StartLocation.id].means.add(Land())
    world[StartLocation.id].items.update([Vegetable(), Cotton()])

    player = PlayerState(send_callback=output)
    player.name = 'Andrey'
    player.bag.update([Vegetable(), Cotton()])
    Chatflow(player, world).start()

    observer = PlayerState(send_callback=observe)
    Chatflow(player, world).spawn(StartLocation)
    observer.name = 'A silent observer'

    peasant = PeasantState()
    StateMutator(peasant, world).spawn(StartLocation)

    player.alive = True
    # s = '/where'

    s = '/start'
    while True:
        chatflow = Chatflow(player, world, command_prefix='/')
        chatflow.process_message(s)

        try:
            # s = raw_input('%s> ' % ' '.join('/' + c for c, h in chatflow.get_commands()))
            s = raw_input('%s> ' % player.input)
        except (EOFError, KeyboardInterrupt):
            break

        peasant.mutator_class(peasant, world).act()

