import collections
from itertools import chain

from .mutators import ActorMutator
from .locations import StartLocation, Direction
from .commodities import ActionClasses, DirtyRags, Weapon
from .states import ActorState
from .npcs import NpcState
from .utils import credits, list_sentence, pretty_list, group_by_class, FilterSet
from .production import MeansOfProduction
from .attacks import HumanAttacks


class CommandPrefix(str):
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
        elif isinstance(arg, str) and arg.isdigit() and arg != '0':
            try:
                name, item = self.bag[int(arg) - 1]
            except IndexError:
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


class Chatflow(ActorMutator, HumanAttacks):

    class UnknownChatflowCommand(Exception):
        pass

    default_wear = DirtyRags
    cooldown_announce = {
        'active': {False: ("falls asleep.", "fall asleep."), 'first': ("wakes up.", "wake up.")}
    }

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
                except self.UnknownChatflowCommand:
                    if 'answered' not in self.actor.input:
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
                self.wakeup()
                return handler(*args, **kwargs)
        raise self.UnknownChatflowCommand

    def reply(self, result):
        if isinstance(result, FilterSet):  # some methods return them
            return
        if isinstance(result, str):
            self.actor.send(result)
        elif isinstance(result, collections.Iterable):
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
        yield (
            'me',
            lambda:
                self.look(self.actor) if self.actor.name
                else self.input('name', self.name, "You didn't introduce yourself yet. Please tell me your name.")())

        if self.actor.alive:
            yield ('restart', self.confirmation('restart', self.die, 'Do you want to restart the game?'))

            yield 'where', lambda: self.where()

            for l in Direction.all:
                yield (
                    l,
                    lambda:
                        self.go(l) if l in self.actor.location.exits
                        else "You can't go %s from here." % l if l in Direction.compass
                        else "You can't %s here." % l)

            yield (
                'look',
                lambda *args:
                    'You look around and think, "There\'s no one here but %sme".' % self.cmd_pfx
                    if not any(self.others)
                    else self.choice('look', self.look, self.others, prompt="whom to look at", skip_single=True)(*args))

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

            yield (
                'attack',
                lambda *args:
                    "There's no one here you can attack."
                    if not any(self.others)
                    else self.choice('attack', self.attack, self.others,
                                     prompt="whom to attack", skip_single=True)(*args))

            attacks = set(self.organic_attacks)
            attacks.update(cls.attack for cls in Weapon.__subclasses__())
            for attack in attacks:
                yield (
                    attack.verb,
                    lambda:
                        "You're not attacking anyone"
                        if not self.actor.victim
                        else f"You fail to {attack} {self.actor.victim.name}." if not self.kick(attack) else None)

            nothing_there = 'There is nothing on the ground that you can pick up.',
            yield (
                'pick',
                lambda *args:
                    self.choice('pick', self.pick, self.location.items, skip_single=True, select_subset=True)(*args)
                    if self.location.items
                    else nothing_there)

            yield (
                'collect',
                lambda:
                    self.pick(self.location.items)
                    if self.location.items
                    else nothing_there)

            yield (
                'bag',
                lambda:
                    self.bag() if self.actor.bag
                    else f'Your bag is empty. You have {credits(self.actor.credits)}.')

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
                        else self.choice(cls.verb, lambda i: getattr(self, cls.verb)(i),
                                         self.actor.bag.filter(cls), skip_single=True)(*args))

            yield (
                'unequip',
                lambda *args: self.unequip(*args) if self.actor.wields else "You aren't wielding anything.")

            for cls in MeansOfProduction.__subclasses__():
                yield (
                    cls.verb,
                    lambda:
                        self.produce(next(self.location.means.filter(cls)))
                        if any(self.location.means.filter(cls))
                        else "You can't {cls.verb} here.")

            yield ('sleep', lambda: self.sleep() if not self.actor.asleep else "You're alreay asleep.")

            return

        yield 'start', self.start
        yield 'name', self.input('name', self.name, "Please tell me your name.")

    def welcome(self):
        yield "Hello and welcome to this little MUD game."

    def name(self, name):
        yield f"Hello, {name}."
        yield f"You can {self.cmd_pfx}start the game now or give me another {self.cmd_pfx}name."
        self.actor.name = name

    def start(self):
        if self.actor.name is None:
            return chain(self.welcome(), [self.dispatch('name')])
        self.spawn(StartLocation)
        return self.where(verb="wake up")

    def help(self):
        commands_list = (self.cmd_pfx + cmd for cmd, hndlr in self.get_commands())
        commands_list = ", ".join(commands_list)
        return f"Known commands are: {commands_list}"

    def look(self, actor):  # TODO: add if actor barters / buys / sells
        if actor == self.actor:
            descr = f"You are {actor.get_full_descr(actor)}."
            if actor.alive:
                yield descr
            else:
                yield "%s You can change your %sname." % (descr, self.cmd_pfx)
                yield "You are dead."
                return
            yield "In your bag you have %s." % pretty_list(actor.bag)
            if actor.wears:
                yield "You wear %s." % actor.wears.descr
            else:
                yield "You are naked."  # shouldn't ever be the case
            if actor.wields:
                yield "You wield %s. You can %sunequip it." % (actor.wields.descr, self.cmd_pfx)
        else:
            yield f"You see {actor.get_full_descr(self.actor)}."
            if actor.wears:
                yield "%s wears %s." % (actor.Name, actor.wears.descr)
            if actor.wields:
                yield "%s wields %s." % (actor.Name, actor.wields.descr)

    def where(self, verb=None):
        actor = self.actor
        location = actor.location
        last_location = actor.last_location

        if not verb:
            verb = ("are still" if last_location and location.descr == last_location.descr
                    else "are")

        actor.last_location = location
        yield f"You {verb} {location.descr}"

        for means in self.location.means:
            yield means.descr % (self.cmd_pfx + means.verb)

        for descr, directions in location.get_exit_groups():
            directions = (self.cmd_pfx + d for d in directions)
            yield descr % list_sentence(directions)

        if len(self.location.items) == 1:
            for item in self.location.items:
                yield f"On the ground you see {item.name}. You can {self.cmd_pfx}pick it up."
        elif len(self.location.items) > 1:
            items_sentence = pretty_list(self.location.items)
            yield f"On the ground you see {items_sentence}. " \
                  f"You can {self.cmd_pfx}pick or {self.cmd_pfx}collect them all."

        others = FilterSet(self.others)
        if others:
            if len(others) > 1:
                yield "You see:"
                actor_groups = (others.filter(cls) for cls in (NpcState, PlayerState))
                for actor_group in actor_groups:
                    for actor in sorted(actor_group, key=lambda a: (type(a).__name__, a.name)):
                        yield f"  • {actor.get_full_descr(self.actor)}"
            else:
                for actor in others:
                    yield f"You see {actor.get_full_descr(self.actor)}."

            actions = [f'take a closer {self.cmd_pfx}look at them']

            if any(a.barters for a in others):
                actions.append(f'{self.cmd_pfx}barter')

            if any(a.sells for a in others):
                actions.append(f'{self.cmd_pfx}buy')

            if any(a.buys for a in others):
                actions.append(f'{self.cmd_pfx}sell')

            actions.append(f'{self.cmd_pfx}attack')

            actions_sentence = list_sentence(actions, glue="or")
            yield f"You can {actions_sentence}."

    def get_barter_chain(self):
        return self.choice_chain(
            'barter',
            self.barter,

            dict(arg='counterparty',
                 bag=(o for o in self.others if o.barters),
                 prompt="whom to barter with",
                 skip_single=True),

            dict(arg='for_what',
                 bag=lambda counterparty: counterparty.bag,
                 prompt="what to barter for"),

            dict(arg='what',
                 bag=self.actor.bag,
                 prompt="what to barter off"))

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
                 prompt="what to sell"))

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
                 prompt="what to buy"))

    def go(self, direction):
        if super(Chatflow, self).go(direction):
            return self.where()

    def pick(self, item_or_items):
        super(Chatflow, self).pick(
            item_or_items, announce=lambda items_str: f'put {items_str} into your {self.cmd_pfx}bag.')

    def unequip(self):
        super(Chatflow, self).unequip(announce=lambda item: f"put {item.name} back into your {self.cmd_pfx}bag.")

    def bag(self):
        actions = ['drop']
        for cls in ActionClasses.__subclasses__():
            if any(self.actor.bag.filter(cls)):
                actions.append(cls.verb)
        actions_sentence = list_sentence((f"{self.cmd_pfx}{a}" for a in actions), glue="or")

        if len(self.actor.bag) == 1:
            item, = self.actor.bag
            yield f"In your bag there's nothing but {item.descr}. You can {actions_sentence} it."
            yield f"You have {credits(self.actor.credits)}."
        else:
            yield "You look into your bag and see:"
            for n, (caption, item) in enumerate(group_by_class(self.actor.bag)):
                yield f"{n + 1:d}. {caption}"

            yield f"You have {credits(self.actor.credits)}."
            yield f"You can {actions_sentence} items."

    def produce(self, means):
        missing = list()
        fruits = super(Chatflow, self).produce(means, missing)

        if not fruits:
            if missing:
                return "You need %s to %s." % (pretty_list(i() for i in missing), means.verb)
            else:
                return "You fail to %s anything." % means.verb

        pronoun = "them" if len(fruits) > 1 else "it"
        return "You %s %s. You put %s into your %sbag." \
               % (means.verb, pretty_list(fruits), pronoun, self.cmd_pfx)

    def deteriorate(self, commodity):
        if super(Chatflow, self).deteriorate(commodity):
            self.actor.send(commodity.deteriorate('Your'))

    def wakeup(self, announce=None):  # called from dispatch
        if self.actor.alive:
            self.set_cooldown('active', 20, announce)

    def spawn(self, location):
        super().spawn(location)
        self.wakeup(announce=False)

    def attack(self, whom):
        methods = self.attack_methods()
        methods = (f"{m} with {self.actor.weapon.name}" if m.is_weapon_method else m for m in methods)
        methods = (f"{self.cmd_pfx}{m}" for m in methods)
        attacks_sentence = list_sentence(methods, glue="or")
        super(Chatflow, self).attack(whom, f'attack {whom.name}. You can {attacks_sentence}.')


class PlayerState(ActorState):
    mutator_class = Chatflow
    definite_name = '(player)'
    max_hitpoints = 5

    def get_mutator(self, world):
        return Chatflow(self, world, self.cmd_pfx)

    def __init__(self, send_callback, cmd_pfx):
        super().__init__()
        self.send = send_callback or (lambda message: None)
        self.cmd_pfx = cmd_pfx
        self.last_location = None
        self.input = {}
        self.chain = {}

    @property
    def recieves_announces(self):
        return self.alive and 'active' in self.cooldown
