from itertools import groupby, chain, izip_longest

from .mutators import pretty_list, StateMutator
from .locations import StartLocation
from .commodities import ActionClasses, Commodity, Vegetable, DirtyRags
from .states import PlayerState, NpcMixin


class CommandPrefix(unicode):
    def is_cmd(self, arg):
        return arg and (not self or arg.startswith(self))

    def get_cmd(self, arg, default=None):
        if self.is_cmd(arg):
            return arg[len(self):].lower()
        return default.lower() if hasattr(default, 'lower') else default


class InputHandler(object):
    def __init__(self, state, command, f, prompt, cmd_pfx):
        self.state = state
        self.command = command
        self.f = f
        self.prompt = prompt
        self.cmd_pfx = cmd_pfx

    def _modify_arg(self, arg):
        if self.cmd_pfx and self.cmd_pfx.is_cmd(arg):
            return
        return arg

    def __call__(self, arg=None):
        arg = self._modify_arg(arg)
        if arg is None:
            self.state.clear()
            self.state.update(command=self.command)
            return self.prompt
        else:
            return self.f(arg)


def bag_display(bag):
    bag = sorted(bag, key=lambda i: i.name)
    if all(isinstance(i, Commodity) for i in bag):
        for item_cls, group in groupby(bag, lambda i: type(i)):
            group = list(group)
            count = len(group)
            if count > 1:
                caption = item_cls.plural % count
            else:
                caption = item_cls.name
            yield caption, group.pop(0)
    else:
        for n, item in enumerate(bag):
            yield item.name, item


class ChoiceHandler(InputHandler):
    def __init__(self, state, command, f, bag, cmd_pfx, prompt=None,
                 select_subset=False, skip_single=False):
        bag = set(bag)
        self.bag = list(bag_display(bag))
        prompt = prompt or "what to %s" % command
        self.prompt_str = "Please choose %s" % prompt
        self.all = select_subset and bag
        self.skip_single = skip_single
        super(ChoiceHandler, self).__init__(state, command, f, self._get_prompt(), cmd_pfx)

    def _get_prompt(self):
        if self.all:
            yield "%s or %s %sall:" % (self.prompt_str, self.command, self.cmd_pfx)
        else:
            yield "%s:" % self.prompt_str
        for n, (caption, item) in enumerate(self.bag):
            yield "%s%d. %s" % (self.cmd_pfx, n + 1, caption)


    def _modify_arg(self, arg):
        arg = self.cmd_pfx.get_cmd(arg, arg)
        if self.all and arg == 'all':
            return self.all

        item = None
        if self.skip_single and len(self.bag) == 1:
            caption, item = self.bag.pop(0)
        elif isinstance(arg, basestring) and arg.isdigit() and arg != '0':
            try:
                name, item = self.bag[int(arg) - 1]
            except:
                pass
        if item:
            return item


class ChoiceChainHandler(ChoiceHandler):
    def __init__(self, state, input_state, command, f, steps, cmd_pfx):
        self.state = state
        self.input_state = input_state
        self.command = command
        self.f = f
        self.steps = list(steps)
        self.cmd_pfx = cmd_pfx
        self.i = 0
        self.next_step = False

    @property
    def args(self):
        if 'args' not in self.state:
            self.state['args'] = {}
        return self.state['args']

    @property
    def cur_step(self):
        return self.steps[self.i]

    @property
    def cur_arg(self):
        return self.cur_step['arg']

    @property
    def cur_bag(self):
        bag = self.cur_step['bag']
        return bag(**self.args) if callable(bag) else bag

    @property
    def cur_check(self):
        check = self.cur_step.get('check')
        if callable(check) and not check(**self.args):
            return False
        return True

    @property
    def skipped(self):
        if 'skipped' not in self.state:
            self.state['skipped'] = {}
        return self.state['skipped']

    @property
    def can_go_back(self):
        if self.i == 0:
            return False
        if all(self.skipped.get(i, False) for i in range(self.i)):
            return False
        return True

    def _store_choice(self, arg):
        self.state['args'][self.cur_arg] = arg
        self.next_step = True


    def __call__(self, arg=None):
        cmd = self.cmd_pfx.get_cmd(arg, arg)
        if cmd == 'cancel':
            self.state.clear()
            return

        while self.i < len(self.steps) and self.cur_arg in self.args:
            self.i += 1

        if cmd == 'back':
            while self.can_go_back:
                if self.i in self.skipped:
                    del self.skipped[self.i]
                self.i -= 1
                del self.state['args'][self.cur_arg]
                if not self.skipped.get(self.i):
                    break

        result = None

        while True:
            if self.i == len(self.steps):  # proceed to end step
                result = self.f(**self.args)
                self.state.clear()
                break

            self.next_step = False

            handler = ChoiceHandler(
                self.input_state, self.command, self._store_choice, self.cur_bag, self.cmd_pfx,
                prompt=self.cur_step.get('prompt'),
                select_subset=self.cur_step.get('select_subset'),
                skip_single=self.cur_step.get('skip_single', False))
            result = handler(arg)

            if not self.next_step:
                if self.can_go_back:
                    footer = "You can go {0}back or {0}cancel.".format(self.cmd_pfx)
                else:
                    footer = "You can %scancel %s." % (self.cmd_pfx, self.command)

                result = chain(result, [footer])
                break

            if not self.cur_check:
                self.state.clear()
                break

            if arg is None:
                self.skipped[self.i] = True
            else:
                arg = None

            self.i += 1

        return result


class ConfirmationHandler(InputHandler):
    def __init__(self, state, command, f, prompt, cmd_pfx):
        super(ConfirmationHandler, self).__init__(
            state, command, cmd_pfx=cmd_pfx,
            f=lambda yes: f() if yes else None,
            prompt="{0} Say {1}yes or {1}no.".format(prompt, cmd_pfx))

    def _modify_arg(self, arg):
        cmd = self.cmd_pfx.get_cmd(arg, arg)
        if cmd == "yes":
            return True
        if cmd == "no":
            return False



class UnknownChatflowCommand(Exception):
    pass


class Chatflow(StateMutator):
    def __init__(self, actor, world, cmd_pfx=None):
        super(Chatflow, self).__init__(actor, world)
        self.cmd_pfx = cmd_pfx or CommandPrefix()


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
                        self.reply("Unknown command. Send %shelp for the list of commands"
                                   % self.cmd_pfx)
                else:
                    if 'answered' in self.actor.input:
                        self.actor.input.clear()


    def tokenize(self, text):
        return text.split(None, 1)


    def get_command_args(self, command, *args):
        if self.cmd_pfx.is_cmd(command):
            yield self.cmd_pfx.get_cmd(command), args

        # additional state mutation iterations

        if 'answered' in self.actor.input:
            yield self.actor.input['command'], [self.actor.input['answered']]


    def dispatch(self, command, *args, **kwargs):
        for cmd, handler in self.get_commands():
            if cmd == command:
                return handler(*args, **kwargs)
        raise UnknownChatflowCommand


    def reply(self, result):
        if isinstance(result, basestring):
            self.actor.send(result)
        elif result is not None:
            self.actor.send("\n".join(result))


    def input(self, command, f, prompt):
        return (
            command,
            InputHandler(self.actor.input, command, f, prompt, cmd_pfx=self.cmd_pfx))


    def choice(self, command, f, bag, **kwargs):
        return (
            command,
            ChoiceHandler(self.actor.input, command, f, bag, cmd_pfx=self.cmd_pfx, **kwargs))


    def choice_chain(self, command, f, *steps):
        return (
            command,
            ChoiceChainHandler(self.actor.chain, self.actor.input, command, f, steps, self.cmd_pfx))


    def confirmation(self, command, f, prompt):
        return (
            command,
            ConfirmationHandler(self.actor.input, command, f, prompt, self.cmd_pfx))


    def get_commands(self):
        yield 'help', self.help

        if self.actor.name:
            yield 'me', lambda: self.look(self.actor)

        if self.actor.alive:
            yield self.confirmation('restart', self.die, "Do you want to restart the game?")

            yield 'where', lambda: self.where(verb="are still")

            for means in self.location.means:
                yield means.verb, lambda: self.produce(means)

            for l in self.actor.location.exits.keys():
                yield l, lambda: self.go(l)

            if self.location.items:
                yield self.choice('pick', self.pick, self.location.items, select_subset=True)
                if len(self.location.items) > 1:
                    yield 'collect', lambda: self.pick(self.location.items)

            others = list(a for a in self.location.actors if a is not self.actor)
            if others:
                yield self.choice('look', self.look, others, prompt="whom to look at",
                                  skip_single=True)

            npcs = self.location.npcs
            if npcs:
                if self.actor.barters:
                    yield self.choice_chain(
                        'barter', self.barter,
                        dict(arg='counterparty',
                             bag=npcs,
                             check=self.barter_counterparty,
                             prompt="whom to barter with",
                             skip_single=True),

                        dict(arg='for_what',
                             bag=lambda counterparty: counterparty.bag,
                             prompt="what to barter for"),

                        dict(arg='what',
                             bag=self.actor.bag,
                             prompt="what to barter off")
                    )
                else:
                    yield 'barter', lambda: 'Your bag is empty, you have nothing to offer.'

            if self.actor.bag:
                yield 'bag', self.bag
                yield self.choice('drop', self.drop, self.actor.bag, select_subset=True)

                for cls in ActionClasses.__subclasses__():
                    items = set(self._items_by_class(cls))
                    if items:
                        yield self.choice(cls.verb, lambda i: self.use_commodity(cls, i), items,
                                          skip_single=True)

            else:
                if self.actor.diamonds:
                    yield 'bag', lambda: 'Your bag is empty. You have %d diamonds.' % self.actor.diamonds
                else:
                    yield 'bag', lambda: 'Your bag is empty and you have no diamonds.'

            return

        yield 'start', self.start
        yield self.input('name', self.name, "Please tell me your name.")


    def welcome(self):
        yield "Hello and welcome to this little MUD game."


    def name(self, name):
        yield "Hello, %s." % name
        yield "You can {0}start the game now " \
              "or give me another {0}name.".format(self.cmd_pfx)
        self.actor.name = name


    def start(self):
        if self.actor.name is None:
            return chain(self.welcome(), [self.dispatch('name')])
        self.spawn(StartLocation)
        return self.where(verb="wake up")


    def spawn(self, location):
        super(Chatflow, self).spawn(location)
        self.actor.wears = DirtyRags()


    def help(self):
        commands_list = (self.cmd_pfx + cmd for cmd, hndlr in self.get_commands())
        return "Known commands are: %s" % ", ".join(commands_list)


    def look(self, actor):
        if actor == self.actor:
            descr = "You are %s." % actor.descr
            if actor.alive:
                yield descr
            else:
                yield "%s You can change your %sname." % (descr, self.cmd_pfx)
                yield "You are dead."
                return
            yield "In your bag you have %s." % pretty_list(actor.bag)
            wear_str = "You wear"
        else:
            yield "You see %s." % actor.descr
            wear_str = "%s wears" % actor.Name
        yield "%s %s." % (wear_str, actor.wears.name)


    def barter(self, counterparty, what, for_what):
        if super(Chatflow, self).barter(counterparty, what, for_what):
            yield 'You barter %s for %s with %s.' \
                  % (pretty_list(what), pretty_list(for_what), counterparty.name)


    def barter_counterparty(self, counterparty):
        if not counterparty.barters:
            self.actor.send("%s doesn't want to barter with you." % counterparty.Name)
            return False
        return True


    def where(self, verb="are"):
        yield 'You %s %s' % (verb, self.actor.location.descr)

        for means in self.location.means:
            yield means.descr % (self.cmd_pfx + means.verb)

        for direction, exit in self.actor.location.exits.iteritems():
            yield exit['descr'] % (self.cmd_pfx + direction)

        if len(self.location.items) == 1:
            for item in self.location.items:
                yield "On the ground you see %s. You can %spick it up." \
                      % (item.name, self.cmd_pfx)
        elif len(self.location.items) > 1:
            yield "On the ground you see {items}. You can {0}pick or {0}collect them all." \
                  .format(self.cmd_pfx, items=pretty_list(self.location.items))

        has_npcs = False
        has_others = False
        for actor in self.location.actors:
            if isinstance(actor, NpcMixin):
                has_npcs = True
            if actor is self.actor:
                continue
            has_others = True
            yield "You see %s." % actor.descr

        actions = []
        if has_others:
            actions.append("take a closer %slook at them" % self.cmd_pfx)
            if has_npcs:
                actions.append("try to %sbarter with them" % self.cmd_pfx)
        if actions:
            if len(actions) == 1:
                actions_str, = actions
            else:
                actions_str = "%s or %s" % (', '.join(n for n in actions[:-1]), actions[-1])
            yield "You can %s." % actions_str


    def go(self, direction):
        if super(Chatflow, self).go(direction):
            return self.where()


    def pick(self, item_or_items):
        items = super(Chatflow, self).pick(item_or_items)
        yield "You put %s into your %sbag." % (pretty_list(items), self.cmd_pfx)


    def drop(self, item_or_items):
        items = super(Chatflow, self).drop(item_or_items)
        yield "You drop %s on the ground." % pretty_list(items)


    def use_commodity(self, cls, item_or_items):
        items = getattr(super(Chatflow, self), cls.verb)(item_or_items)
        yield "You %s %s." % (cls.verb, pretty_list(items))


    def bag(self):
        diamonds_message = None
        if self.actor.diamonds:
            diamonds_message = "You have %d diamonds." % self.actor.diamonds
        else:
            diamonds_message = "You have no diamonds."

        if len(self.actor.bag) == 1:
            item, = self.actor.bag
            yield "In your bag there's nothing but %s. You can %sdrop it." \
                  % (item.name, self.cmd_pfx)
            yield diamonds_message
        else:
            yield "You look into your bag and see:"
            seen_cls = {cls: False for cls in ActionClasses.__subclasses__()}
            for n, (caption, item) in enumerate(bag_display(self.actor.bag)):
                caption = "%d. %s" % (n + 1, caption)
                for cls, seen in seen_cls.iteritems():
                    if isinstance(item, cls) and not seen:
                        caption += " you can %s%s" % (self.cmd_pfx, cls.verb)
                        seen_cls[cls] = True
                yield caption
            yield diamonds_message
            yield "You can %sdrop any item." % self.cmd_pfx


    def die(self):
        super(Chatflow, self).die()
        return "You die."


    def produce(self, means):
        missing = list()
        fruit = super(Chatflow, self).produce(means, missing)

        if fruit is None:
            if missing:
                return "You need %s to %s." % (pretty_list(missing), means.verb)
            else:
                return "You fail to %s anything." % means.verb

        return "You %s %s. You put it into your %sbag." \
               % (means.verb, fruit.name, self.cmd_pfx)
