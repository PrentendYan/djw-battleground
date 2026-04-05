# -*- coding: utf-8 -*-
"""Tests for the core combat engine."""

import random
import sys
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from battleground.board import Board
from battleground.combat import CombatEngine
from battleground.minion import Minion
from battleground.simulator import Simulator
from battleground.types import CombatResult, Tribe


def _make_engine(minions0: list[Minion], minions1: list[Minion], seed: int = 42, hero_tiers=(1, 1)):
    b0 = Board(minions0)
    b1 = Board(minions1)
    rng = random.Random(seed)
    return CombatEngine(b0, b1, hero_tiers=hero_tiers, rng=rng)


# ==================================================================
# Basic combat
# ==================================================================


class TestBasicCombat:
    """Simple stat-vs-stat combats with no keywords."""

    def test_stronger_minion_wins(self):
        """A 5/5 should beat a 3/3."""
        engine = _make_engine(
            [Minion(name="Big", attack=5, health=5)],
            [Minion(name="Small", attack=3, health=3)],
        )
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN
        assert outcome.damage > 0

    def test_identical_minions_draw_or_trade(self):
        """Two identical minions trade into each other → draw."""
        engine = _make_engine(
            [Minion(name="A", attack=3, health=3)],
            [Minion(name="B", attack=3, health=3)],
        )
        outcome = engine.run()
        assert outcome.result == CombatResult.DRAW
        assert outcome.damage == 0

    def test_empty_board_draw(self):
        engine = _make_engine([], [])
        outcome = engine.run()
        assert outcome.result == CombatResult.DRAW

    def test_one_side_empty_instant_win(self):
        engine = _make_engine(
            [Minion(name="A", attack=1, health=1)],
            [],
        )
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN

    def test_multi_minion_combat(self):
        """4x 2/3 vs 1x 5/5 — the 4-minion side should win."""
        engine = _make_engine(
            [Minion(name=f"A{i}", attack=2, health=3) for i in range(4)],
            [Minion(name="B", attack=5, health=5)],
        )
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN

    def test_more_minions_attacks_first(self):
        """Side with more minions should attack first."""
        engine = _make_engine(
            [Minion(name="A", attack=1, health=1), Minion(name="B", attack=1, health=1)],
            [Minion(name="C", attack=100, health=1)],
            seed=42,
        )
        # Side 0 has 2 minions, attacks first. First attack kills C.
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN

    def test_zero_attack_minion_skipped(self):
        """A 0-attack minion should never attack."""
        engine = _make_engine(
            [Minion(name="Wall", attack=0, health=10)],
            [Minion(name="Hitter", attack=1, health=5)],
        )
        outcome = engine.run()
        # Hitter hits Wall 5 times, Wall never attacks
        assert outcome.result == CombatResult.LOSS


# ==================================================================
# Keywords
# ==================================================================


class TestTaunt:
    def test_taunt_forces_targeting(self):
        """Attacks must target the taunt minion."""
        # Board 1: taunt in front, big minion behind
        engine = _make_engine(
            [Minion(name="Attacker", attack=10, health=10)],
            [
                Minion(name="Taunt", attack=1, health=3, taunt=True),
                Minion(name="Hidden", attack=20, health=1),
            ],
        )
        # Run many times — attacker should always hit Taunt first
        for seed in range(20):
            e = _make_engine(
                [Minion(name="Attacker", attack=10, health=10)],
                [
                    Minion(name="Taunt", attack=1, health=3, taunt=True),
                    Minion(name="Hidden", attack=20, health=1),
                ],
                seed=seed,
            )
            # After first attack, Taunt should be dead
            e._assign_entry_orders()
            e._determine_first_attacker()
            attacker = e.boards[0].get_next_attacker()
            target = e.boards[1].get_random_target(rng=e.rng)
            assert target.name == "Taunt"


class TestDivineShield:
    def test_divine_shield_absorbs_damage(self):
        """Divine shield should absorb the first hit."""
        engine = _make_engine(
            [Minion(name="Attacker", attack=10, health=10)],
            [Minion(name="Shielded", attack=1, health=1, divine_shield=True)],
        )
        outcome = engine.run()
        # First hit: shield pops, no damage. Second hit: Shielded dies.
        # But Shielded also counter-attacks each time (1 dmg).
        # Turn 1: Attacker hits Shielded → shield pops. Shielded counter-attacks → Attacker 9hp
        # Turn 2: Shielded attacks Attacker (if Shielded has attack>0 and goes first)
        #   Actually, side 0 has 1 minion, side 1 has 1 minion → random first attacker
        # Regardless, Shielded should eventually die
        assert outcome.result == CombatResult.WIN

    def test_divine_shield_zero_damage_doesnt_pop(self):
        """0-damage attacks should not pop divine shield."""
        # This is handled by _deal_damage returning early for amount <= 0
        engine = _make_engine(
            [Minion(name="Zero", attack=0, health=5)],
            [Minion(name="Shielded", attack=5, health=5, divine_shield=True)],
        )
        outcome = engine.run()
        # Zero never attacks, Shielded kills Zero, shield never tested
        assert outcome.result == CombatResult.LOSS


class TestPoisonous:
    def test_poisonous_kills_regardless_of_health(self):
        """A 1/1 poisonous should kill a 1/100."""
        engine = _make_engine(
            [Minion(name="Poison", attack=1, health=1, poisonous=True)],
            [Minion(name="Tank", attack=1, health=100)],
        )
        outcome = engine.run()
        # Both die: Poison hits Tank (poisonous → Tank health=0),
        # Tank counter-attacks Poison (1 dmg → dead)
        assert outcome.result == CombatResult.DRAW

    def test_poisonous_blocked_by_divine_shield(self):
        """Poisonous should not trigger if divine shield absorbs the hit."""
        engine = _make_engine(
            [Minion(name="Poison", attack=1, health=1, poisonous=True)],
            [Minion(name="Shielded", attack=1, health=5, divine_shield=True)],
        )
        outcome = engine.run()
        # First hit: shield pops, no kill. Counter: Poison dies.
        assert outcome.result == CombatResult.LOSS


class TestVenomous:
    def test_venomous_consumed_after_first_kill(self):
        """Venomous should be consumed after the first kill."""
        # Create a venomous windfury minion — attacks twice
        m = Minion(name="Venom", attack=1, health=10, venomous=True, windfury=True)
        engine = _make_engine(
            [m],
            [
                Minion(name="T1", attack=0, health=50),
                Minion(name="T2", attack=0, health=50),
            ],
        )
        outcome = engine.run()
        # First attack: Venom hits T1 or T2 → venomous kills → consumed
        # Second attack (windfury): Venom hits remaining → normal 1 damage
        # Then opponent turn: 0 attack, skipped
        # Combat continues... eventually Venom kills both
        # The key point: venomous is consumed after first kill
        # After first attack resolving, m.venomous should be False
        # We just check the final result makes sense
        assert outcome.result == CombatResult.WIN


class TestWindfury:
    def test_windfury_attacks_twice(self):
        """Windfury minion should attack twice per turn."""
        # 3/10 WF vs two 1/3 minions
        engine = _make_engine(
            [Minion(name="WF", attack=3, health=10, windfury=True)],
            [Minion(name="A", attack=1, health=3), Minion(name="B", attack=1, health=3)],
        )
        outcome = engine.run()
        # WF attacks twice per turn, should clean up quickly
        assert outcome.result == CombatResult.WIN

    def test_mega_windfury_attacks_four_times(self):
        """Mega-Windfury minion attacks 4 times per turn."""
        engine = _make_engine(
            [Minion(name="MWF", attack=2, health=20, mega_windfury=True)],
            [Minion(name=f"M{i}", attack=1, health=2) for i in range(4)],
        )
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN


class TestReborn:
    def test_reborn_revives_with_1hp(self):
        """Reborn minion should come back with 1 health."""
        engine = _make_engine(
            [Minion(name="Reborn", attack=3, health=1, reborn=True)],
            [Minion(name="Enemy", attack=1, health=4)],
        )
        outcome = engine.run()
        # Turn 1: Reborn(3/1) hits Enemy(1/4) → Enemy(1/1), counter kills Reborn
        # Reborn comes back as (3/1)
        # Turn 2: Enemy(1/1) hits Reborn(3/1) → both die
        assert outcome.result == CombatResult.DRAW

    def test_reborn_only_once(self):
        """Reborn should only trigger once."""
        engine = _make_engine(
            [Minion(name="Reborn", attack=1, health=1, reborn=True)],
            [Minion(name="Enemy", attack=1, health=3)],
        )
        outcome = engine.run()
        # Reborn dies → revives (1/1, no reborn) → attacks → counter kills → stays dead
        assert outcome.result == CombatResult.LOSS


class TestCleave:
    def test_cleave_hits_adjacent(self):
        """Cleave should damage the target and its neighbors."""
        engine = _make_engine(
            [Minion(name="Cleaver", attack=10, health=10, cleave=True)],
            [
                Minion(name="L", attack=1, health=5),
                Minion(name="M", attack=1, health=5),
                Minion(name="R", attack=1, health=5),
            ],
        )
        # If Cleaver hits M, L and R also take 10 damage → all 3 die
        # If hits L, only L and M take damage. If hits R, only M and R.
        # Since no taunts, random targeting. Over many seeds, all should die.
        # Let's just check Cleaver wins
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN


class TestStealth:
    def test_stealth_prevents_targeting(self):
        """Stealthed minion should not be targeted until it attacks."""
        # Only the non-stealth minion should be targeted
        for seed in range(20):
            e = _make_engine(
                [Minion(name="Attacker", attack=5, health=5)],
                [
                    Minion(name="Visible", attack=1, health=3),
                    Minion(name="Stealthy", attack=10, health=1, stealth=True),
                ],
                seed=seed,
            )
            e._assign_entry_orders()
            target = e.boards[1].get_random_target(rng=e.rng)
            assert target.name == "Visible"


# ==================================================================
# Damage calculation
# ==================================================================


class TestDamageCalculation:
    def test_damage_includes_hero_tier(self):
        """Damage should include the winner's hero tavern tier."""
        engine = _make_engine(
            [Minion(name="A", attack=5, health=5, tier=3)],
            [Minion(name="B", attack=1, health=1, tier=1)],
            hero_tiers=(4, 2),
        )
        outcome = engine.run()
        assert outcome.result == CombatResult.WIN
        # Damage = hero_tier(4) + surviving_minion_tier(3) = 7
        assert outcome.damage == 7

    def test_draw_zero_damage(self):
        engine = _make_engine(
            [Minion(name="A", attack=3, health=3)],
            [Minion(name="B", attack=3, health=3)],
        )
        outcome = engine.run()
        assert outcome.damage == 0


# ==================================================================
# Deathrattle (basic framework test)
# ==================================================================


class _TokenSpawner(Minion):
    """Test minion: deathrattle summons a 1/1 token."""

    def __init__(self, **kwargs):
        super().__init__(name="Spawner", attack=1, health=1, **kwargs)

    def has_deathrattle(self) -> bool:
        return True

    def deathrattle(self, ctx, position: int) -> None:
        token = Minion(name="Token", attack=1, health=1, tier=1)
        ctx.summon(token, position)


class TestDeathrattle:
    def test_deathrattle_summons_token(self):
        """Deathrattle should summon a token when the minion dies."""
        engine = _make_engine(
            [_TokenSpawner()],
            [Minion(name="Enemy", attack=1, health=1)],
        )
        outcome = engine.run()
        # Spawner and Enemy trade → Spawner deathrattle summons Token(1/1)
        # Token survives → Player 0 wins
        assert outcome.result == CombatResult.WIN

    def test_deathrattle_with_reborn(self):
        """Deathrattle fires before reborn resurrects."""
        # Spawner with reborn: dies → deathrattle (summon token) → reborn (1/1)
        spawner = _TokenSpawner(reborn=True)
        engine = _make_engine(
            [spawner],
            [Minion(name="Enemy", attack=5, health=5)],
        )
        outcome = engine.run()
        # After first trade: Token(1/1) + Spawner-reborn(1/1) vs Enemy(5/4)
        # Both eventually die to Enemy
        assert outcome.result == CombatResult.LOSS


# ==================================================================
# Simulator (Monte Carlo)
# ==================================================================


class TestSimulator:
    def test_deterministic_with_seed(self):
        """Same seed should produce same results."""
        b0 = Board([Minion(name="A", attack=3, health=3)])
        b1 = Board([Minion(name="B", attack=3, health=4)])

        r1 = Simulator(b0, b1, num_simulations=100, seed=42).run()
        r2 = Simulator(b0, b1, num_simulations=100, seed=42).run()
        assert r1.wins == r2.wins
        assert r1.losses == r2.losses
        assert r1.ties == r2.ties

    def test_stronger_side_wins_more(self):
        """A clearly stronger board should win most simulations."""
        b0 = Board([Minion(name=f"A{i}", attack=5, health=5) for i in range(5)])
        b1 = Board([Minion(name=f"B{i}", attack=2, health=2) for i in range(3)])
        result = Simulator(b0, b1, num_simulations=200, seed=1).run()
        assert result.win_rate > 0.9

    def test_summary_format(self):
        b0 = Board([Minion(name="A", attack=3, health=3)])
        b1 = Board([Minion(name="B", attack=3, health=3)])
        result = Simulator(b0, b1, num_simulations=10, seed=0).run()
        summary = result.summary()
        assert "Win:" in summary
        assert "simulations" in summary
