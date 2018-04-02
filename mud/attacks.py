class Attack:
    def __init__(self, verb, verb_s, damage, cooldown_time, is_weapon_method=False):
        self.verb = verb
        self.verb_s = verb_s
        self.damage = damage
        self.cooldown_time = cooldown_time
        self.is_weapon_method = is_weapon_method

    def __str__(self):
        return self.verb


Punch = Attack('punch', 'punches', damage=1, cooldown_time=1)
Bite = Attack('bites', 'bites', damage=1, cooldown_time=1)
Kick = Attack('kick', 'kicks', damage=1, cooldown_time=2)
Bash = Attack('bash', 'bashes', damage=3, cooldown_time=2, is_weapon_method=True)


class HumanAttacks:
    organic_attacks = {Kick, Punch}

    def attack_methods(self):
        yield Kick
        if self.actor.wields:
            if self.actor.weapon:
                yield self.actor.weapon.attack
        else:
            yield Punch


class OrganicAttacks:
    def attack_methods(self):
        return self.organic_attacks
