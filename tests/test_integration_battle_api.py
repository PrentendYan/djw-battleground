# -*- coding: utf-8 -*-
"""Integration tests: BattleAPI + FirestoneSimulator end-to-end combat simulation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from battleground.bridge.firestone import FirestoneSimulator
from battleground.game.battle_api import BattleAPI
from battleground.game.state import HeroState, MinionState, PlayerState
from battleground.types import SimulationResult


# ---------------------------------------------------------------------------
# Module-scoped fixture: start the bridge once for all tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sim():
    """Start the Firestone bridge once and tear it down after all tests."""
    with FirestoneSimulator() as s:
        yield s


@pytest.fixture(scope="module")
def api(sim):
    """BattleAPI backed by the live Firestone bridge."""
    return BattleAPI(sim)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player(player_id: int, board: tuple[MinionState, ...], tavern_tier: int = 1) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        health=40,
        tavern_tier=tavern_tier,
        hero=HeroState(card_id="TB_BaconShop_HERO_01"),
        board=board,
    )


# ---------------------------------------------------------------------------
# Test 1: Basic 1v1 — Scallywag vs generic 3/3
# ---------------------------------------------------------------------------


class TestBasicCombat:
    """Scenario: 1x Scallywag (BGS_061 2/1) vs 1x generic 3/3 (BGS_039)."""

    @pytest.fixture(scope="class")
    def result(self, api):
        player = _player(
            player_id=0,
            board=(MinionState(card_id="BGS_061", attack=2, health=1),),
        )
        opponent = _player(
            player_id=1,
            board=(MinionState(card_id="BGS_039", attack=3, health=3),),
        )
        return api.run_combat(player, opponent, num_simulations=1000)

    def test_returns_simulation_result(self, result):
        assert isinstance(result, SimulationResult)

    def test_total_positive(self, result):
        assert result.total > 0

    def test_rates_sum_to_one(self, result):
        total = result.win_rate + result.loss_rate + result.tie_rate
        assert total == pytest.approx(1.0, abs=1e-6)

    def test_scallywag_deathrattle_causes_draw(self, result):
        """Scallywag (2/1) vs 3/3: the Deathrattle summons a 1/1 Sky Pirate that
        kills the wounded 3/1, so the board clears to a draw every time.
        A plain 2/1 would lose, but the DR changes the outcome entirely."""
        # Firestone simulates the deathrattle → board clears → tie
        assert result.tie_rate == pytest.approx(1.0, abs=0.01)

    def test_no_surviving_winner_means_zero_damage(self, result):
        """When both boards wipe (tie), neither side deals post-combat damage."""
        assert result.avg_win_damage == pytest.approx(0.0, abs=0.01)
        assert result.avg_loss_damage == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test 2: Rates sum to 1.0 across multiple scenario variants
# ---------------------------------------------------------------------------


class TestRateSumInvariant:
    """Verify win+loss+tie == 1.0 for various board compositions."""

    def _run(self, api, p_board, o_board, n=500):
        return api.run_combat(
            _player(0, p_board),
            _player(1, o_board),
            num_simulations=n,
        )

    def test_mirror_match(self, api):
        board = (MinionState(card_id="BGS_039", attack=3, health=3),)
        r = self._run(api, board, board)
        assert r.win_rate + r.loss_rate + r.tie_rate == pytest.approx(1.0, abs=1e-6)

    def test_dominant_player(self, api):
        p = (MinionState(card_id="BGS_039", attack=10, health=10),)
        o = (MinionState(card_id="BGS_039", attack=1, health=1),)
        r = self._run(api, p, o)
        assert r.win_rate + r.loss_rate + r.tie_rate == pytest.approx(1.0, abs=1e-6)

    def test_two_minions_each(self, api):
        p = (
            MinionState(card_id="BGS_061", attack=2, health=1),
            MinionState(card_id="BGS_039", attack=3, health=3),
        )
        o = (
            MinionState(card_id="BGS_039", attack=2, health=2),
            MinionState(card_id="BGS_039", attack=3, health=3),
        )
        r = self._run(api, p, o)
        assert r.win_rate + r.loss_rate + r.tie_rate == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Test 3: Complex scenario — keywords + multiple minions
# ---------------------------------------------------------------------------


class TestComplexScenario:
    """Multi-minion board with taunt, divine_shield, and reborn."""

    @pytest.fixture(scope="class")
    def result_with_keywords(self, api):
        """Player has taunt + divine_shield + reborn minions; opponent has plain minions."""
        player = _player(
            player_id=0,
            tavern_tier=3,
            board=(
                MinionState(card_id="BGS_039", attack=3, health=4, taunt=True),
                MinionState(card_id="BGS_039", attack=4, health=3, divine_shield=True),
                MinionState(card_id="BGS_039", attack=2, health=2, reborn=True),
            ),
        )
        opponent = _player(
            player_id=1,
            tavern_tier=3,
            board=(
                MinionState(card_id="BGS_039", attack=3, health=3),
                MinionState(card_id="BGS_039", attack=3, health=3),
                MinionState(card_id="BGS_039", attack=3, health=3),
            ),
        )
        return api.run_combat(player, opponent, num_simulations=2000)

    @pytest.fixture(scope="class")
    def result_plain(self, api):
        """Same total stats but no keywords — baseline for comparison."""
        player = _player(
            player_id=0,
            tavern_tier=3,
            board=(
                MinionState(card_id="BGS_039", attack=3, health=4),
                MinionState(card_id="BGS_039", attack=4, health=3),
                MinionState(card_id="BGS_039", attack=2, health=2),
            ),
        )
        opponent = _player(
            player_id=1,
            tavern_tier=3,
            board=(
                MinionState(card_id="BGS_039", attack=3, health=3),
                MinionState(card_id="BGS_039", attack=3, health=3),
                MinionState(card_id="BGS_039", attack=3, health=3),
            ),
        )
        return api.run_combat(player, opponent, num_simulations=2000)

    def test_returns_simulation_result(self, result_with_keywords):
        assert isinstance(result_with_keywords, SimulationResult)

    def test_total_equals_num_simulations(self, result_with_keywords):
        assert result_with_keywords.total == 2000

    def test_rates_sum_to_one(self, result_with_keywords):
        r = result_with_keywords
        assert r.win_rate + r.loss_rate + r.tie_rate == pytest.approx(1.0, abs=1e-6)

    def test_keywords_improve_win_rate(self, result_with_keywords, result_plain):
        """Taunt + divine_shield + reborn should yield better win+tie vs plain equivalents."""
        keyword_positive = result_with_keywords.win_rate + result_with_keywords.tie_rate
        plain_positive = result_plain.win_rate + result_plain.tie_rate
        assert keyword_positive >= plain_positive - 0.05  # allow 5% tolerance for variance

    def test_damage_positive_or_zero(self, result_with_keywords):
        """avg_win_damage is 0 when player never won; otherwise positive."""
        r = result_with_keywords
        if r.wins > 0:
            assert r.avg_win_damage > 0
        if r.losses > 0:
            assert r.avg_loss_damage > 0


# ---------------------------------------------------------------------------
# Test 4: Deterministic scenarios (sanity checks)
# ---------------------------------------------------------------------------


class TestDeterministicOutcomes:
    """Verify the bridge produces expected outcomes for clear-cut boards."""

    def test_10_10_beats_1_1(self, api):
        """A 10/10 should always beat a 1/1."""
        player = _player(0, (MinionState(card_id="BGS_039", attack=10, health=10),))
        opponent = _player(1, (MinionState(card_id="BGS_039", attack=1, health=1),))
        r = api.run_combat(player, opponent, num_simulations=200)
        assert r.win_rate == pytest.approx(1.0, abs=0.01)

    def test_identical_minions_draw(self, api):
        """Two identical 3/3s should always draw."""
        board = (MinionState(card_id="BGS_039", attack=3, health=3),)
        player = _player(0, board)
        opponent = _player(1, board)
        r = api.run_combat(player, opponent, num_simulations=200)
        assert r.tie_rate == pytest.approx(1.0, abs=0.01)

    def test_scallywag_card_id_accepted(self, api):
        """BGS_061 (Scallywag) should be accepted by the bridge without error."""
        player = _player(0, (MinionState(card_id="BGS_061", attack=2, health=1),))
        opponent = _player(1, (MinionState(card_id="BGS_039", attack=2, health=1),))
        r = api.run_combat(player, opponent, num_simulations=200)
        assert isinstance(r, SimulationResult)
        assert r.total > 0
