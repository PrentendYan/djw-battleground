# -*- coding: utf-8 -*-
"""Integration tests for the Firestone Node.js bridge."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from battleground.bridge import FirestoneSimulator


@pytest.fixture(scope="module")
def sim():
    """Shared simulator instance for all tests in this module."""
    s = FirestoneSimulator()
    s.start()
    yield s
    s.shutdown()


# ==================================================================
# Basic connectivity
# ==================================================================


class TestBridgeConnectivity:
    def test_bridge_starts_and_loads_cards(self, sim):
        assert sim._ready is True

    def test_get_card_by_id(self, sim):
        card = sim.get_card("BGS_061")
        assert card["name"] == "Scallywag"
        assert card["attack"] >= 1
        assert card["health"] >= 1

    def test_get_card_not_found(self, sim):
        with pytest.raises(Exception):
            sim.get_card("NONEXISTENT_CARD_ID_12345")

    def test_get_bg_cards_returns_list(self, sim):
        cards = sim.get_bg_cards()
        assert len(cards) > 500
        assert all(c["techLevel"] > 0 for c in cards)

    def test_bg_cards_have_required_fields(self, sim):
        cards = sim.get_bg_cards()
        sample = cards[0]
        for field in ["id", "name", "attack", "health", "techLevel"]:
            assert field in sample


# ==================================================================
# Simple simulations
# ==================================================================


class TestSimpleSimulations:
    def test_stronger_side_wins(self, sim):
        """A 10/10 should always beat a 1/1."""
        p = [sim.make_board_entity("BGS_039", 10, 10, 1)]
        o = [sim.make_board_entity("BGS_039", 1, 1, 2, friendly=False)]
        battle = sim.make_battle_info(p, o, num_simulations=100)
        r = sim.simulate(battle)
        assert r.win_rate == 1.0

    def test_identical_1v1_is_draw(self, sim):
        """Two identical minions should always draw."""
        p = [sim.make_board_entity("BGS_039", 3, 3, 1)]
        o = [sim.make_board_entity("BGS_039", 3, 3, 2, friendly=False)]
        r = sim.simulate(sim.make_battle_info(p, o, num_simulations=200))
        assert r.tie_rate == 1.0

    def test_divine_shield_advantage(self, sim):
        """5/5 DS vs 5/5 — DS should win 100%."""
        p = [sim.make_board_entity("BGS_039", 5, 5, 1, divine_shield=True)]
        o = [sim.make_board_entity("BGS_039", 5, 5, 2, friendly=False)]
        r = sim.simulate(sim.make_battle_info(p, o, num_simulations=500))
        assert r.win_rate == 1.0

    def test_damage_is_positive_on_win(self, sim):
        """Winner should deal positive damage."""
        p = [sim.make_board_entity("BGS_039", 10, 10, 1)]
        o = [sim.make_board_entity("BGS_039", 1, 1, 2, friendly=False)]
        battle = sim.make_battle_info(p, o, player_tier=4, num_simulations=100)
        r = sim.simulate(battle)
        assert r.avg_win_damage > 0


# ==================================================================
# Complex effects (deathrattles, reborn, etc.)
# ==================================================================


class TestComplexEffects:
    def test_deathrattle_minion_has_impact(self, sim):
        """Board with deathrattle minion should lose less than vanilla."""
        # Harvest Golem (2/3, DR: summon 2/1) vs 2/4
        # Vanilla 2/3 vs 2/4: vanilla trades and loses (2/3 hits 2/4→2/1, counter 2→2/1, then 2/1 kills 2/1, draw)
        # With DR, the token gives an edge
        p_dr = [sim.make_board_entity("EX1_556", 2, 3, 1)]
        p_vanilla = [sim.make_board_entity("BGS_039", 2, 3, 1)]
        o = [sim.make_board_entity("BGS_039", 2, 4, 2, friendly=False)]

        r_dr = sim.simulate(sim.make_battle_info(p_dr, o, num_simulations=2000))
        r_vanilla = sim.simulate(sim.make_battle_info(p_vanilla, o, num_simulations=2000))

        # Deathrattle board should have better outcomes (higher win+tie rate)
        assert (r_dr.win_rate + r_dr.tie_rate) >= (r_vanilla.win_rate + r_vanilla.tie_rate)

    def test_poisonous_kills_big_minion(self, sim):
        """1/1 Poisonous should trade with 100/100."""
        p = [sim.make_board_entity("BGS_039", 1, 1, 1, poisonous=True)]
        o = [sim.make_board_entity("BGS_039", 100, 100, 2, friendly=False)]
        r = sim.simulate(sim.make_battle_info(p, o, num_simulations=500))
        # Both should die → draw
        assert r.tie_rate == pytest.approx(1.0, abs=0.01)

    def test_reborn_provides_advantage(self, sim):
        """Reborn 3/1 should beat vanilla 3/1 vs a 1/3."""
        p_reborn = [sim.make_board_entity("BGS_039", 3, 1, 1, reborn=True)]
        p_vanilla = [sim.make_board_entity("BGS_039", 3, 1, 1)]
        o = [sim.make_board_entity("BGS_039", 1, 3, 2, friendly=False)]

        r_reborn = sim.simulate(sim.make_battle_info(p_reborn, o, num_simulations=1000))
        r_vanilla = sim.simulate(sim.make_battle_info(p_vanilla, o, num_simulations=1000))

        # Reborn version should win more
        assert r_reborn.win_rate >= r_vanilla.win_rate

    def test_taunt_affects_outcome(self, sim):
        """Taunt should change combat outcome vs no-taunt."""
        # Taunt(1/10) + Big(10/1) vs 5/5
        # With taunt: 5/5 forced to hit taunt → protects nothing actually → draw
        # Without taunt: 50% chance 5/5 kills 10/1, 50% chance it hits 1/10 → variable
        p_with_taunt = [
            sim.make_board_entity("BGS_039", 1, 10, 1, taunt=True),
            sim.make_board_entity("BGS_039", 10, 1, 2),
        ]
        p_no_taunt = [
            sim.make_board_entity("BGS_039", 1, 10, 1),
            sim.make_board_entity("BGS_039", 10, 1, 2),
        ]
        o = [sim.make_board_entity("BGS_039", 5, 5, 3, friendly=False)]

        r_taunt = sim.simulate(sim.make_battle_info(p_with_taunt, o, num_simulations=2000))
        r_no = sim.simulate(sim.make_battle_info(p_no_taunt, o, num_simulations=2000))

        # Taunt changes the distribution — outcomes should differ
        assert abs(r_taunt.win_rate - r_no.win_rate) > 0.01 or abs(r_taunt.tie_rate - r_no.tie_rate) > 0.01


# ==================================================================
# Performance
# ==================================================================


class TestPerformance:
    def test_7v7_completes_in_time(self, sim):
        """7v7 with 10k sims should complete in < 5 seconds."""
        import time

        p = [sim.make_board_entity("BGS_039", 3 + i, 4 + i, i + 1) for i in range(7)]
        o = [sim.make_board_entity("BGS_039", 3 + i, 4 + i, i + 8, friendly=False) for i in range(7)]
        battle = sim.make_battle_info(p, o, player_tier=5, opponent_tier=5, num_simulations=10000)

        start = time.perf_counter()
        r = sim.simulate(battle, timeout=10.0)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0
        assert r.total == 10000


# ==================================================================
# SimulationResult
# ==================================================================


class TestSimulationResult:
    def test_summary_string(self, sim):
        p = [sim.make_board_entity("BGS_039", 5, 5, 1)]
        o = [sim.make_board_entity("BGS_039", 3, 3, 2, friendly=False)]
        r = sim.simulate(sim.make_battle_info(p, o, num_simulations=100))
        s = r.summary()
        assert "Win:" in s
        assert "simulations" in s
