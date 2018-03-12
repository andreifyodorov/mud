# coding: utf8
from itertools import groupby, chain, izip_longest

from .mutators import StateMutator
from .locations import StartLocation
from .commodities import ActionClasses, Commodity, Vegetable, DirtyRags
from .states import PlayerState, NpcMixin
from .utils import list_sentence, pretty_list, group_by_class, FilterSet


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


class ChoiceHandler(InputHandler):
    def __init__(self, state, command, f, bag, cmd_pfx, prompt=None,
                 select_subset=False, skip_single=False):
        bag = set(bag)
        self.bag = list(group_by_class(bag))
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
                    footer = "You can %scancel the %s." % (self.cmd_pfx, self.command)

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
    default_wear = DirtyRags

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
                        self.actor.chain.clear()


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


    def input(self, cmd, f, prompt):
        return InputHandler(self.actor.input, cmd, f, prompt, cmd_pfx=self.cmd_pfx)


    def choice(self, cmd, f, bag, **kwargs):
        return ChoiceHandler(self.actor.input, cmd, f, bag, cmd_pfx=self.cmd_pfx, **kwargs)


    def choice_chain(self, cmd, f, *steps):
        return ChoiceChainHandler(self.actor.chain, self.actor.input, cmd, f, steps, self.cmd_pfx)


    def confirmation(self, cmd, f, prompt):
        return ConfirmationHandler(self.actor.input, cmd, f, prompt, self.cmd_pfx)


    def get_commands(self):
        yield 'help', self.help

        if self.actor.name:
            yield 'me', lambda: self.look(self.actor)

        if self.actor.alive:
            yield (
                'restart',
                self.confirmation('restart', self.die, 'Do you want to restart the game?'))

            yield 'where', lambda: self.where(verb='are still')

            for l in self.actor.location.exits.keys():
                yield l, lambda: self.go(l)

            yield (
                'look',
                lambda *args:
                    'You look around and think, "There\'s no one here but %sme".' % self.cmd_pfx
                    if not any(self.others)
                    else self.choice('look', self.look, self.others,
                                     prompt="whom to look at", skip_single=True)(*args))

            yield (
                'barter',
                lambda *args:
                    "There's no one here you can barter with."
                    if not any(o.barters for o in self.others)
                    else 'Your bag is empty, you have nothing to offer.' if not self.actor.bag
                    else self.get_barter_chain()(*args))

            yield (
                'sell',
                lambda *args:
                    "There's no one here you can sell to."
                    if not any(o.buys for o in self.others)
                    else 'Your bag is empty, you have nothing to sell.' if not self.actor.bag
                    else self.get_sell_chain()(*args))

            yield (
                'buy',
                lambda *args:
                    "There's no one here you can buy from."
                    if not any(o.sells for o in self.others)
                    else 'Your have no credits to buy anything.' if not self.actor.credits
                    else self.get_buy_chain()(*args))


            nothing_there = 'There is nothing on the ground that you can pick up.',
            yield (
                'pick',
                lambda *args:
                    self.choice('pick', self.pick, self.location.items, select_subset=True)(*args)
                    if self.location.items
                    else nothing_there)

            yield (
                'collect',
                lambda: self.pick(self.location.items)
                    if self.location.items
                    else nothing_there)

            yield (
                'bag',
                lambda:
                    self.bag() if self.actor.bag
                    else 'Your bag is empty. You have %d credits.' % self.actor.credits
                    if self.actor.credits
                    else 'Your bag is empty and you have no credits.')

            yield (
                'drop',
                lambda *args:
                    "Your bag is already empty."
                    if not self.actor.bag
                    else self.choice('drop', self.drop, self.actor.bag, select_subset=True)(*args))

            for cls in ActionClasses.__subclasses__():
                yield (
                    cls.verb,
                    lambda *args:
                        "You have nothing you can %s." % cls.verb
                        if not any(self.actor.bag.filter(cls))
                        else self.choice(cls.verb, lambda i: self.use_commodity(cls, i),
                                         self.actor.bag.filter(cls), skip_single=True)(*args))

            for means in self.location.means:
                yield means.verb, lambda: self.produce(means)

            return

        yield 'start', self.start
        yield 'name', self.input('name', self.name, "Please tell me your name.")


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


    def help(self):
        commands_list = (self.cmd_pfx + cmd for cmd, hndlr in self.get_commands())
        return "Known commands are: %s" % ", ".join(commands_list)


    def look(self, actor):  #TODO: add if actor barters / buys / sells
        if actor == self.actor:
            descr = "You are %s." % actor.descr
            if actor.alive:
                yield descr
            else:
                yield "%s You can change your %sname." % (descr, self.cmd_pfx)
                yield "You are dead."
                return
            yield "In your bag you have %s." % pretty_list(actor.bag)
            if actor.wears:
                yield "You wear %s." % actor.wears.name
            else:
                yield "You are naked."
        else:
            yield "You see %s." % actor.descr
            if actor.wears:
                yield "%s wears %s." % (actor.Name, actor.wears.name)
            else:
                yield "%s is naked." % actor.Name


    def get_barter_chain(self):
        return self.choice_chain(
            'barter',
            self.barter,

            dict(arg='counterparty',
                 bag=(o for o in self.others if o.barters),
                 # check=self.barter_counterparty,  #TODO: looks like we don't need this check
                 prompt="whom to barter with",
                 skip_single=True),

            dict(arg='for_what',
                 bag=lambda counterparty: counterparty.bag,
                 prompt="what to barter for"),

            dict(arg='what',
                 bag=self.actor.bag,
                 prompt="what to barter off")
        )


    # def barter_counterparty(self, counterparty):
    #     if not counterparty.barters:
    #         self.actor.send("%s doesn't want to barter with you." % counterparty.Name)
    #         return False
    #     return True


    def barter(self, counterparty, what, for_what):
        if super(Chatflow, self).barter(counterparty, what, for_what):
            yield 'You barter %s for %s with %s.' \
                  % (pretty_list(what), pretty_list(for_what), counterparty.name)


    def get_sell_chain(self):
        return self.choice_chain(
            'sell',
            self.sell,

            dict(arg='counterparty',
                 bag=(o for o in self.others if o.buys),
                 prompt="whom to sell to",
                 skip_single=True),

            dict(arg="what",
                 bag=self.actor.bag,
                 prompt="what to sell")
        )


    def sell(self, counterparty, what):
        if super(Chatflow, self).sell(counterparty, what):
            yield 'You sell %s to %s for %d credits.' \
                  % (pretty_list(what), counterparty.name,
                     1 if isinstance(what, Commodity) else len(what))


    def get_buy_chain(self):
        return self.choice_chain(
            'buy',
            self.buy,

            dict(arg='counterparty',
                 bag=(o for o in self.others if o.buys),
                 prompt="whom to buy from",
                 skip_single=True),

            dict(arg="what",
                 bag=lambda counterparty: counterparty.for_sale,
                 prompt="what to buy")
        )


    def buy(self, counterparty, what):
        if super(Chatflow, self).buy(counterparty, what):
            yield 'You buy %s from %s for %d credits.' \
                  % (pretty_list(what), counterparty.name,
                     1 if isinstance(what, Commodity) else len(what))


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

        others = FilterSet(self.others)
        if others:
            if len(others) > 1:
                yield "You see people:"
                actor_groups = (others.filter(cls) for cls in (NpcMixin, PlayerState))
                for actor_group in actor_groups:
                    for actor in sorted(actor_group, key=lambda a: a.name):
                        yield u"  • %s" % actor.descr
            else:
                for actor in others:
                    yield "You see %s." % actor.descr

            actions = ['take a closer %slook at them']
            if any(a.barters for a in others):
                actions.append('%sbarter')
            if any(a.sells for a in others):
                actions.append('%sbuy')
            if any(a.buys for a in others):
                actions.append('%ssell')

            actions = (a % self.cmd_pfx for a in actions)
            yield "You can %s." % (list_sentence(actions, glue="or"))


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
        credits_message = None
        if self.actor.credits > 1:
            credits_message = "You have %d credits." % self.actor.credits
        elif self.actor.credits == 1:
            credits_message = "You have 1 credit."
        else:
            credits_message = "You have no credits."

        actions = ['drop']
        for cls in ActionClasses.__subclasses__():
            if any(self.actor.bag.filter(cls)):
                actions.append(cls.verb)
        actions_sentence = list_sentence(("%s%s" % (self.cmd_pfx, a) for a in actions), glue="or")

        if len(self.actor.bag) == 1:
            item, = self.actor.bag
            yield "In your bag there's nothing but %s. You can %s it."  \
                % (item.name, actions_sentence)
            yield credits_message
        else:
            yield "You look into your bag and see:"
            for n, (caption, item) in enumerate(group_by_class(self.actor.bag)):
                yield "%d. %s" % (n + 1, caption)

            yield credits_message
            yield "You can %s items." % actions_sentence


    def die(self):
        super(Chatflow, self).die()
        return "You die."


    def produce(self, means):
        missing = list()
        fruits = super(Chatflow, self).produce(means, missing)

        if not fruits:
            if missing:
                return "You need %s to %s." % (pretty_list(missing), means.verb)
            else:
                return "You fail to %s anything." % means.verb

        return "You %s %s. You put it into your %sbag." \
               % (means.verb, pretty_list(fruits), self.cmd_pfx)

    def deteriorate(self, commodity):
        super(Chatflow, self).deteriorate(commodity)
        if hasattr(commodity, 'deteriorates_into'):
            self.actor.send(
                "%s turns into %s." % (commodity.Name, commodity.deteriorates_into.name))
        else:
            self.actor.send("%s disintegrates." % commodity.Name)
