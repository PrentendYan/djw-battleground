# -*- coding: utf-8 -*-
"""Tests for ShopState and refresh_shop."""

from __future__ import annotations

import random

import pytest

from battleground.game.minion_pool import MinionPool, MinionTemplate
from battleground.game.shop import SHOP_SIZES, ShopState, refresh_shop


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def pool() -> MinionPool:
    templates = {
        "T1_A": MinionTemplate("T1_A", "A", 1, 1, 1),
        "T1_B": MinionTemplate("T1_B", "B", 2, 2, 1),
        "T2_A": MinionTemplate("T2_A", "C", 3, 3, 2),
    }
    return MinionPool.from_templates(templates)


# ── ShopState unit tests ─────────────────────────────────────────────

class TestShopState:
    def test_size(self) -> None:
        shop = ShopState(minion_ids=("a", "b", "c"))
        assert shop.size == 3

    def test_is_valid_index(self) -> None:
        shop = ShopState(minion_ids=("a", "b"))
        assert shop.is_valid_index(0)
        assert shop.is_valid_index(1)
        assert not shop.is_valid_index(2)
        assert not shop.is_valid_index(-1)

    def test_remove_at(self) -> None:
        shop = ShopState(minion_ids=("a", "b", "c"))
        new_shop = shop.remove_at(1)
        assert new_shop.minion_ids == ("a", "c")

    def test_toggle_freeze(self) -> None:
        shop = ShopState(minion_ids=("a",), frozen=False)
        frozen = shop.toggle_freeze()
        assert frozen.frozen is True
        unfrozen = frozen.toggle_freeze()
        assert unfrozen.frozen is False


class TestShopSizes:
    def test_tier_1_offers_3(self) -> None:
        assert SHOP_SIZES[1] == 3

    def test_tier_2_3_offers_4(self) -> None:
        assert SHOP_SIZES[2] == 4 and SHOP_SIZES[3] == 4

    def test_tier_4_5_offers_5(self) -> None:
        assert SHOP_SIZES[4] == 5 and SHOP_SIZES[5] == 5

    def test_tier_6_offers_6(self) -> None:
        assert SHOP_SIZES[6] == 6


# ── refresh_shop tests ───────────────────────────────────────────────

class TestRefreshShop:
    def test_first_refresh_no_current(self, pool: MinionPool) -> None:
        rng = random.Random(42)
        new_pool, shop = refresh_shop(pool, 1, None, rng)
        assert shop.size == 3  # tier 1 → 3 minions
        assert not shop.frozen

    def test_refresh_returns_old_minions_to_pool(self, pool: MinionPool) -> None:
        rng = random.Random(42)
        _, shop1 = refresh_shop(pool, 1, None, rng)
        # Now refresh again — old minions should be returned
        pool_after, shop2 = refresh_shop(pool, 1, shop1, rng)
        # Total pool stock should stay the same (drawn then returned then drawn again)
        total_t1 = sum(pool_after.stock[c] for c in pool_after.stock if pool_after.templates[c].tier <= 1)
        # We drew 3 fresh, so total should be initial - 3
        initial_t1 = sum(pool.stock[c] for c in pool.stock if pool.templates[c].tier <= 1)
        assert total_t1 == initial_t1 - 3

    def test_refresh_with_higher_tier(self, pool: MinionPool) -> None:
        rng = random.Random(42)
        _, shop = refresh_shop(pool, 2, None, rng)
        assert shop.size == 4  # tier 2 → 4 minions
