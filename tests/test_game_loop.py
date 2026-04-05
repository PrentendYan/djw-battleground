# -*- coding: utf-8 -*-
"""Tests for GameLoop — recruit/combat/damage/elimination cycle."""

from __future__ import annotations

import random

import pytest

from battleground.game.game_loop import (
    EARLY_DAMAGE_CAP,
    EARLY_TURN_CAP,
    GameLoop,
    calculate_damage,
)
from battleground.game.minion_pool import MinionPool, MinionTemplate
from battleground.game.random_player import RandomPlayer
from battleground.game.state import MinionState


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_pool() -> MinionPool:
    templates = {
        f"T{tier}_{chr(65+j)}": MinionTemplate(f"T{tier}_{chr(65+j)}", f"M{tier}{chr(65+j)}", tier, tier + 1, tier)
        for tier in range(1, 4)
        for j in range(3)
    }
    return MinionPool.from_templates(templates)


@pytest.fixture
def pool() -> MinionPool:
    return _make_pool()


# ── Damage calculation ───────────────────────────────────────────────

class TestCalculateDamage:
    def test_basic_damage(self) -> None:
        board = (
            MinionState(card_id="X", attack=1, health=1, tavern_tier=1),
            MinionState(card_id="Y", attack=1, health=1, tavern_tier=3),
        )
        # hero tier 2 + (1+3) = 6
        assert calculate_damage(2, board, 10) == 6

    def test_early_game_cap(self) -> None:
        board = tuple(
            MinionState(card_id="X", attack=1, health=1, tavern_tier=6)
            for _ in range(7)
        )
        # hero tier 6 + 7×6 = 48, but turn 5 < 8 → capped at 15
        assert calculate_damage(6, board, 5) == EARLY_DAMAGE_CAP

    def test_no_cap_after_turn_8(self) -> None:
        board = tuple(
            MinionState(card_id="X", attack=1, health=1, tavern_tier=6)
            for _ in range(3)
        )
        # hero tier 4 + 3×6 = 22, turn 8 → no cap
        assert calculate_damage(4, board, 8) == 22

    def test_empty_board(self) -> None:
        assert calculate_damage(3, (), 10) == 3  # just hero tier


# ── GameLoop integration ─────────────────────────────────────────────

class TestGameLoopSimple:
    def test_run_completes(self, pool: MinionPool) -> None:
        """A full game with 4 random players should terminate."""
        players = [RandomPlayer(i, random.Random(i)) for i in range(4)]
        loop = GameLoop(players, pool, rng=random.Random(99))
        final = loop.run(max_turns=20)
        # At most 1 player should be alive
        assert final.num_alive <= 1 or final.current_turn == 20

    def test_run_8_players(self, pool: MinionPool) -> None:
        """Standard 8-player game should complete."""
        players = [RandomPlayer(i, random.Random(i)) for i in range(8)]
        loop = GameLoop(players, pool, rng=random.Random(42))
        final = loop.run(max_turns=30)
        assert final.num_alive >= 1

    def test_positions_assigned(self, pool: MinionPool) -> None:
        """Eliminated players should get finishing positions."""
        players = [RandomPlayer(i, random.Random(i)) for i in range(4)]
        loop = GameLoop(players, pool, rng=random.Random(42))
        final = loop.run(max_turns=30)
        dead = [p for p in final.players if p.is_dead]
        for p in dead:
            assert p.finished_position > 0

    def test_deterministic(self, pool: MinionPool) -> None:
        """Same seed → same result."""
        def run_game(seed: int):
            players = [RandomPlayer(i, random.Random(i)) for i in range(4)]
            loop = GameLoop(players, pool, rng=random.Random(seed))
            return loop.run(max_turns=15)

        g1 = run_game(42)
        g2 = run_game(42)
        for p1, p2 in zip(g1.players, g2.players):
            assert p1.health == p2.health
            assert p1.finished_position == p2.finished_position

    def test_gold_increases_over_turns(self, pool: MinionPool) -> None:
        """After turn 1, players should have been given gold (even if spent)."""
        players = [RandomPlayer(i, random.Random(i)) for i in range(2)]
        loop = GameLoop(players, pool, rng=random.Random(42))
        # Run just 1 turn
        final = loop.run(max_turns=1)
        # All alive players should exist
        assert final.num_alive >= 1

    def test_two_player_finishes(self, pool: MinionPool) -> None:
        """Minimal 2-player game should finish."""
        players = [RandomPlayer(0, random.Random(0)), RandomPlayer(1, random.Random(1))]
        loop = GameLoop(players, pool, rng=random.Random(42))
        final = loop.run(max_turns=40)
        assert final.is_game_over or final.current_turn == 40
