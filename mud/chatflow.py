from .mutators import pretty_list, StateMutator
from .commodities import Vegetable

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
        if super(Chatflow, self).go(direction):
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
        if fruit is None:
            return "You fail to %s anything." % means.verb
        else:
            return "You %s %s. You put it into your %sbag." \
                   % (means.verb, fruit.name, self.command_prefix)
