from collections import namedtuple


class Attack(namedtuple('BaseAttack', ['verb', 'verb_s', 'damage', 'cooldown_time'])):
    def __str__(self):
        return self.verb


Punch = Attack('punch', 'punches', damage=1, cooldown_time=1)
Bite = Attack('bites', 'bites', damage=1, cooldown_time=1)
Kick = Attack('kick', 'kicks', damage=1, cooldown_time=2)
Bash = Attack('bash', 'bashes', damage=3, cooldown_time=2)


class HumanAttacks(object):
    organic_attacks = {Kick, Punch}

    def attack_methods(self):
        yield Kick
        if self.actor.wields:
            if self.actor.weapon:
                yield self.actor.weapon.attack
        else:
            yield Punch


class OrganicAttacks(object):
    def attack_methods(self):
        return self.organic_attacks
