import collections
from itertools import chain

from .mutators import ActorMutator
from .locations import StartLocation, Direction
from .commodities import ActionClasses, DirtyRags, Weapon
from .states import ActorState
from .npcs import HumanNpcState
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
        self.aborted = False

    def _modify_arg(self, arg):
        if self.cmd_pfx and self.cmd_pfx.is_cmd(arg):
            return
        return arg

    def _should_abort(self):
        return

    def __call__(self, arg=None):
        abort_message = self._should_abort()
        if abort_message:
            self.state.clear()
            self.aborted = True
            return abort_message

        arg = self._modify_arg(arg)
        if arg is None:
            self.state.clear()
            self.state.update(command=self.command)
            return self.prompt
        else:
            return self.f(arg)


class ChoiceHandler(InputHandler):
    def __init__(self, state, command, f, bag, cmd_pfx, prompt=None, full_prompt=None, empty_message=None,
                 select_subset=False, skip_single=False):
        self.bag = bag

        if full_prompt:
            self.prompt_str = full_prompt
        else:
            prompt = prompt or f"what to {command}"
            self.prompt_str = f"Please choose {prompt}"

        self.empty_message = empty_message
        self.select_subset = select_subset
        self.skip_single = skip_single
        super(ChoiceHandler, self).__init__(state, command, f, self._get_prompt(), cmd_pfx)

    def _should_abort(self):
        if not self.bag:
            return self.empty_message or self.bag.empty_message % self.command

    def _get_display_list(self):
        if "bag" not in self.state:
            self.state.update(bag=self.bag)
        return self.state["bag"].get_display_list()

    def _get_prompt(self):
        if self.select_subset:
            yield f"{self.prompt_str} or {self.command} {self.cmd_pfx}all:"
        else:
            yield f"{self.prompt_str}:"

        for n, (caption, item) in enumerate(self._get_display_list()):
            yield f"{self.cmd_pfx}{n + 1:d}. {caption}"

    def _modify_arg(self, arg):
        arg = self.cmd_pfx.get_cmd(arg, arg)
        if self.select_subset and arg == 'all':
            return self.bag

        item = None
        if self.skip_single and len(self.bag) == 1:
            item = self.bag.pop()
            self.state.clear()  # skip_single won't trigger regular clean up

        elif isinstance(arg, str) and arg.isdigit() and arg != '0':
            display_list = self._get_display_list()
            try:
                name, item = display_list[int(arg) - 1]
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

    def get_cur(self, key, default=None):
        value = self.cur_step.get(key, default)
        return value(**self.args) if callable(value) else value

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
                prompt=self.get_cur('prompt'),
                full_prompt=self.get_cur('full_prompt'),
                empty_message=self.get_cur('empty_message'),
                select_subset=self.get_cur('select_subset'),
                skip_single=self.get_cur('skip_single', False))
            result = handler(arg)

            if handler.aborted:
                break

            if not self.next_step:
                if self.can_go_back:
                    footer = "You can go {0}back or {0}cancel.".format(self.cmd_pfx)
                else:
                    footer = "You can %scancel the %s." % (self.cmd_pfx, self.command)

                result = chain(result, [footer])
                break

            if not self.get_cur('check', True):
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
                        self.reply(f"Unknown command. Send {self.cmd_pfx}help for the list of commands.")
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

    def get_commands_by_category(self):
        if self.actor.alive:
            return collections.OrderedDict(
                location=self.get_location_commands(),
                social=self.get_social_commands(),
                inventory=self.get_inventory_commands(),
                produce=self.get_production_commands(),
                general=self.get_alive_general_commands())
        else:
            return dict(general=self.get_dead_general_commands())

    def get_commands(self):
        return chain.from_iterable(self.get_commands_by_category().values())

    def get_me_command(self):
        if self.actor.name:
            return lambda: self.look(self.actor)
        else:
            return self.input('name', self.name, "You didn't introduce yourself yet. Please tell me your name.")

    def get_alive_general_commands(self):
        yield 'me', self.get_me_command()
        yield 'restart', self.confirmation('restart', self.die, 'Do you want to restart the game?')
        yield 'help', self.help

    def get_dead_general_commands(self):
        yield 'start', self.start
        yield 'name', self.input('name', self.name, "Please tell me your name.")
        yield 'me', self.get_me_command()
        yield 'help', self.help

    def get_exit_command(self, l):
        def exit():
            if l in self.actor.location.exits:
                return self.go(l)
            else:
                if l in Direction.compass:
                    return f"You can't go {l} from here."
                else:
                    return f"You can't {l} here."
        return exit

    def get_location_commands(self):
        for l in Direction.all:
            yield l, self.get_exit_command(l)
        yield 'where', lambda: self.where()

    def ActorSet(self, iterable):
        return ActorSet(iterable, perspective=self.actor)

    def get_look_command(self):
        return self.choice(
            'look',
            self.look,
            self.ActorSet(self.others),
            skip_single=True,
            prompt="whom to look at",
            empty_message=f'You look around and think, "There\'s no one here but {self.cmd_pfx}me".')

    def get_barter_command(self):
        return self.choice_chain(
            'barter',
            self.barter,

            dict(arg='counterparty',
                 bag=self.ActorSet(o for o in self.others if o.barters),
                 prompt="whom to barter with",
                 empty_message="There's no one here you can barter with.",
                 skip_single=True),

            dict(arg='for_what',
                 bag=lambda counterparty: CommoditySet(counterparty.bag),
                 full_prompt=lambda counterparty: f"{counterparty.Name} offers you to choose what to barter for"),

            dict(arg='what',
                 bag=CommoditySet(self.actor.bag),
                 prompt=lambda counterparty, for_what: f"what to barter off for {for_what.name}",
                 empty_message="Your bag is empty, you have nothing to offer in exchange."))

    def get_sell_command(self):
        return self.choice_chain(
            'sell',
            self.sell,

            dict(arg='counterparty',
                 bag=self.ActorSet(o for o in self.others if o.buys),
                 prompt="whom to sell to",
                 empty_message="There's no one here you can sell to.",
                 skip_single=True),

            dict(arg="what",
                 bag=CommoditySet(self.actor.bag),
                 prompt="what to sell",
                 empty_message="Your bag is empty, you have nothing to sell."))

    def get_buy_command(self):
        if self.actor.credits:
            return self.choice_chain(
                'buy',
                self.buy,

                dict(arg='counterparty',
                     bag=self.ActorSet(o for o in self.others if o.buys),
                     prompt="whom to buy from",
                     empty_message="There's no one here you can buy from.",
                     skip_single=True),

                dict(arg="what",
                     bag=lambda counterparty: CommoditySet(counterparty.for_sale),
                     prompt="what to buy"))
        else:
            return lambda: 'Your have no credits to buy anything.'

    def get_attack_command(self):
        return self.choice(
            'attack',
            self.attack,
            self.ActorSet(self.others),
            prompt="whom to attack",
            empty_message="There's no one here you can attack.")

    def get_social_commands(self):
        yield 'look', self.get_look_command()
        yield 'barter', self.get_barter_command()
        yield 'sell', self.get_sell_command()
        yield 'buy', self.get_buy_command()
        yield 'attack', self.get_attack_command()

        attacks = set(self.organic_attacks)
        attacks.update(cls.attack for cls in Weapon.__subclasses__())
        if not self.actor.victim:
            for attack in attacks:
                yield attack.verb, lambda: "You're not attacking anyone."
        else:
            for attack in attacks:
                yield attack.verb, lambda: self.kick(attack)

    def get_pick_command(self):
        return self.choice(
            'pick',
            self.pick,
            CommoditySet(self.location.items),
            skip_single=True,
            select_subset=True)

    def get_drop_command(self):
        return self.choice(
            'drop',
            self.drop,
            CommoditySet(self.actor.bag),
            select_subset=True,
            empty_message="Your bag is already empty.")

    def get_commodity_action_command(self, cls):
        return self.choice(
            cls.verb,
            lambda item: getattr(self, cls.verb)(item),
            CommoditySet(self.actor.bag.filter(cls)),
            empty_message="You have nothing you can %s." % cls.verb,
            skip_single=True)

    def get_inventory_commands(self):
        yield 'bag', self.bag

        if self.location.items:
            yield 'pick', self.get_pick_command()
            yield 'collect', lambda: self.pick(self.location.items)
        else:
            for cmd in ('pick', 'collect'):
                yield cmd, 'There is nothing on the ground that you can pick up.'

        yield 'drop', self.get_drop_command()

        for cls in ActionClasses.__subclasses__():
            yield cls.verb, self.get_commodity_action_command(cls)

        yield 'unequip', self.unequip

    def get_production_commands(self):
        for cls in MeansOfProduction.__subclasses__():
            yield cls.verb, lambda: self.produce(cls)

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
            descr = f"You are {actor.descr}."
            if self.actor.alive:
                yield descr
            else:
                yield f"{descr} You can change your {self.cmd_pfx}name."
            doing_descr = actor.get_doing_descr()
            if doing_descr:
                yield f"You are {doing_descr}."
            if not actor.alive:
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

        others = self.ActorSet(self.others)
        if others:
            if len(others) > 1:
                yield "You see:"
                for name, actor in others.get_display_list():
                    yield f"  • {actor.get_full_descr(self.actor)}"
            else:
                actor, = others
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

    def go(self, direction):
        if super().go(direction):
            return self.where()

    def pick(self, item_or_items):
        super().pick(item_or_items, announce=lambda items_str: f'put {items_str} into your {self.cmd_pfx}bag.')

    def unequip(self):
        if not self.actor.wields:
            return "You aren't wielding anything."
        super().unequip(announce=lambda item: f"put {item.name} back into your {self.cmd_pfx}bag.")

    def bag(self):
        if not self.bag:
            yield f'Your bag is empty. You have {credits(self.actor.credits)}.'
            return

        actions = ['drop']
        for cls in ActionClasses.__subclasses__():
            if any(self.actor.bag.filter(cls)):
                actions.append(cls.verb)
        actions_sentence = list_sentence((f"{self.cmd_pfx}{a}" for a in actions), glue="or")

        if len(self.actor.bag) == 1:
            item, = self.actor.bag
            yield f"You have nothing but {item.descr} in your bag. You can {actions_sentence} it."
            yield f"You have {credits(self.actor.credits)}."
        else:
            yield "You look into your bag and see:"
            for n, (caption, item) in enumerate(CommoditySet(self.actor.bag).get_display_list()):
                yield f"{n + 1:d}. {caption}"
            yield f"You can {actions_sentence} items."
            yield f"You have {credits(self.actor.credits)}."

    def produce(self, means_cls):
        means = next(self.location.means.filter(means_cls), None)
        if not means:
            return f"You can't {means_cls.verb} anything here."

        missing = list()
        fruits = super(Chatflow, self).produce(means, missing)

        if not fruits:
            if missing:
                missing_str = pretty_list(i() for i in missing)
                return f"You need {missing_str} to {means.verb}."
            else:
                return f"You fail to {means.verb} anything."

        pronoun = "them" if len(fruits) > 1 else "it"
        fruits_str = pretty_list(fruits)
        return f"You {means.verb} {fruits_str}. You put {pronoun} into your {self.cmd_pfx}bag."

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

    def kick(self, method):
        weapon = self.actor.weapon
        if method.is_weapon_method and (not weapon or weapon.attack is not method):
            with_ = self.actor.wields.name if self.actor.wields else 'bare hands'
            return f"You can't {method.verb} with {with_}."
        if not super().kick(method):
            return f"You fail to {method.verb} {self.actor.victim.name}."


class CommoditySet(FilterSet):
    empty_message = "Nothing to %s."

    def get_display_list(self):
        return list(group_by_class(self))


class ActorSet(FilterSet):
    empty_message = "Nobody to %s."

    def __init__(self, iterable, perspective):
        super().__init__(iterable)
        self.perspective = perspective

    def sort_key(self, actor):
        flags = (
            actor.victim and actor.victim is self.perspective,
            actor.victim is not None,
            isinstance(actor, PlayerState),
            isinstance(actor, HumanNpcState))
        return tuple(not flag for flag in flags) + (actor.name_without_icon.lower(),)

    def get_display_list(self):
        result = []
        for actor in sorted(list(self), key=self.sort_key):
            result.append((actor.name, actor))
        return result


class PlayerState(ActorState):
    mutator_class = Chatflow
    definite_name = '(player)'

    def get_mutator(self, world):
        return Chatflow(self, world, self.cmd_pfx)

    def __init__(self, send_callback, cmd_pfx):
        super().__init__()
        self.send = send_callback or (lambda message: None)
        self.cmd_pfx = cmd_pfx
        self.last_location = None
        self.input = {}
        self.chain = {}
        self.counters = {}  # TODO: remove after migrating to v. 9

    @property
    def recieves_announces(self):
        return self.alive and 'active' in self.cooldown
