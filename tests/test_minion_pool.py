# -*- coding: utf-8 -*-
"""Tests for MinionPool — pool creation, take, return, roll."""

from __future__ import annotations

import random

import pytest

from battleground.game.minion_pool import MinionPool, MinionTemplate


# ── Fixtures ─────────────────────────────────────────────────────────

def _make_templates() -> dict[str, MinionTemplate]:
    """Small test pool: 3 tier-1, 2 tier-2, 1 tier-3 minion types."""
    return {
        "T1_A": MinionTemplate("T1_A", "Tabbycat", 1, 1, 1),
        "T1_B": MinionTemplate("T1_B", "Sellemental", 2, 2, 1),
        "T1_C": MinionTemplate("T1_C", "Swampstriker", 1, 2, 1),
        "T2_A": MinionTemplate("T2_A", "Nathrezim", 2, 3, 2),
        "T2_B": MinionTemplate("T2_B", "Harvest Golem", 2, 3, 2),
        "T3_A": MinionTemplate("T3_A", "Deflect-o-Bot", 3, 2, 3),
    }


@pytest.fixture
def pool() -> MinionPool:
    return MinionPool.from_templates(_make_templates())


# ── Tests ────────────────────────────────────────────────────────────

class TestMinionPoolCreation:
    def test_from_templates_stock_counts(self, pool: MinionPool) -> None:
        assert pool.stock_count("T1_A") == 16  # tier 1 → 16 copies
        assert pool.stock_count("T2_A") == 15  # tier 2 → 15
        assert pool.stock_count("T3_A") == 13  # tier 3 → 13

    def test_from_cards_filters_non_pool(self) -> None:
        cards = [
            {"id": "BG001", "type": "Minion", "isBaconPool": True,
             "techLevel": 1, "attack": 1, "health": 1, "name": "Test"},
            {"id": "HERO_01", "type": "Hero", "isBaconPool": False},
            {"id": "SPELL_01", "type": "Battleground_spell"},
        ]
        pool = MinionPool.from_cards(cards)
        assert len(pool.templates) == 1
        assert "BG001" in pool.templates

    def test_get_template(self, pool: MinionPool) -> None:
        t = pool.get_template("T1_A")
        assert t is not None
        assert t.attack == 1 and t.health == 1 and t.tier == 1

    def test_get_template_missing(self, pool: MinionPool) -> None:
        assert pool.get_template("NONEXISTENT") is None


class TestMinionPoolTake:
    def test_take_decrements(self, pool: MinionPool) -> None:
        before = pool.stock_count("T1_A")
        after_pool = pool.take("T1_A")
        assert after_pool.stock_count("T1_A") == before - 1

    def test_take_does_not_mutate_original(self, pool: MinionPool) -> None:
        before = pool.stock_count("T1_A")
        pool.take("T1_A")
        assert pool.stock_count("T1_A") == before

    def test_take_empty_raises(self, pool: MinionPool) -> None:
        p = pool
        for _ in range(16):
            p = p.take("T1_A")
        assert p.stock_count("T1_A") == 0
        with pytest.raises(ValueError):
            p.take("T1_A")


class TestMinionPoolReturn:
    def test_return_increments(self, pool: MinionPool) -> None:
        p = pool.take("T1_A")
        p2 = p.return_minion("T1_A")
        assert p2.stock_count("T1_A") == pool.stock_count("T1_A")

    def test_return_caps_at_max(self, pool: MinionPool) -> None:
        p = pool.return_minion("T1_A")  # already at max
        assert p.stock_count("T1_A") == 16  # tier-1 max

    def test_return_unknown_card_is_noop(self, pool: MinionPool) -> None:
        p = pool.return_minion("GOLDEN_SPECIAL")
        assert p is pool  # same object — no change


class TestAvailableByTier:
    def test_tier1_only(self, pool: MinionPool) -> None:
        ids = pool.available_by_tier(1)
        assert set(ids) == {"T1_A", "T1_B", "T1_C"}

    def test_tier2_includes_lower(self, pool: MinionPool) -> None:
        ids = pool.available_by_tier(2)
        assert "T1_A" in ids and "T2_A" in ids
        assert "T3_A" not in ids

    def test_depleted_excluded(self, pool: MinionPool) -> None:
        p = pool
        for _ in range(16):
            p = p.take("T1_A")
        assert "T1_A" not in p.available_by_tier(1)


class TestRollShop:
    def test_roll_returns_correct_count(self, pool: MinionPool) -> None:
        rng = random.Random(42)
        new_pool, drawn = pool.roll_shop(1, 3, rng)
        assert len(drawn) == 3

    def test_roll_decrements_stock(self, pool: MinionPool) -> None:
        rng = random.Random(42)
        total_before = sum(pool.stock[cid] for cid in pool.stock if pool.templates[cid].tier <= 1)
        new_pool, drawn = pool.roll_shop(1, 3, rng)
        total_after = sum(new_pool.stock[cid] for cid in new_pool.stock if new_pool.templates[cid].tier <= 1)
        assert total_after == total_before - 3

    def test_roll_respects_tier(self, pool: MinionPool) -> None:
        rng = random.Random(42)
        _, drawn = pool.roll_shop(1, 10, rng)
        for cid in drawn:
            assert pool.templates[cid].tier <= 1

    def test_roll_empty_pool(self) -> None:
        t = {"X": MinionTemplate("X", "X", 1, 1, 1)}
        pool = MinionPool(stock={"X": 0}, templates=t)
        rng = random.Random(42)
        _, drawn = pool.roll_shop(1, 3, rng)
        assert len(drawn) == 0

    def test_roll_deterministic_with_seed(self, pool: MinionPool) -> None:
        _, d1 = pool.roll_shop(2, 4, random.Random(99))
        _, d2 = pool.roll_shop(2, 4, random.Random(99))
        assert d1 == d2
