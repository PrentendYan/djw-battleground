# -*- coding: utf-8 -*-
"""Tests for recruit phase — gold, buy/sell, upgrade, freeze, triple."""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from battleground.game.actions import (
    BuyMinionAction,
    EndTurnAction,
    FreezeTavernAction,
    PlayMinionAction,
    RefreshTavernAction,
    SellHandMinionAction,
    SellMinionAction,
    UpgradeTavernAction,
)
from battleground.game.minion_pool import MinionPool, MinionTemplate
from battleground.game.recruit import (
    BUY_COST,
    MAX_BOARD,
    MAX_HAND,
    MAX_TIER,
    REFRESH_COST,
    SELL_VALUE,
    UPGRADE_BASE_COSTS,
    check_triple,
    process_action,
    start_recruit_turn,
    turn_gold,
    upgrade_cost,
)
from battleground.game.shop import ShopState
from battleground.game.state import MinionState, PlayerState


# ── Fixtures ─────────────────────────────────────────────────────────

def _templates() -> dict[str, MinionTemplate]:
    return {
        "T1_A": MinionTemplate("T1_A", "Tabbycat", 1, 1, 1),
        "T1_B": MinionTemplate("T1_B", "Sellemental", 2, 2, 1),
        "T2_A": MinionTemplate("T2_A", "Nathrezim", 2, 3, 2),
    }


@pytest.fixture
def pool() -> MinionPool:
    return MinionPool.from_templates(_templates())


@pytest.fixture
def player() -> PlayerState:
    return PlayerState(player_id=0, health=40, tavern_tier=1, gold=5)


@pytest.fixture
def shop() -> ShopState:
    return ShopState(minion_ids=("T1_A", "T1_B", "T2_A"))


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


# ── Gold calculation ─────────────────────────────────────────────────

class TestTurnGold:
    def test_turn_1_gives_3(self) -> None:
        assert turn_gold(1) == 3

    def test_turn_5_gives_7(self) -> None:
        assert turn_gold(5) == 7

    def test_turn_8_gives_10(self) -> None:
        assert turn_gold(8) == 10

    def test_cap_at_10(self) -> None:
        assert turn_gold(15) == 10


# ── Upgrade cost ─────────────────────────────────────────────────────

class TestUpgradeCost:
    def test_tier1_no_discount(self) -> None:
        assert upgrade_cost(1, 0) == 6

    def test_tier1_with_discount(self) -> None:
        assert upgrade_cost(1, 3) == 3

    def test_discount_floors_at_zero(self) -> None:
        assert upgrade_cost(1, 100) == 0

    def test_max_tier_returns_999(self) -> None:
        assert upgrade_cost(MAX_TIER, 0) == 999


# ── Start recruit turn ───────────────────────────────────────────────

class TestStartRecruitTurn:
    def test_gold_set(self, player: PlayerState, pool: MinionPool, rng: random.Random) -> None:
        p, shop, _, _ = start_recruit_turn(player, None, pool, 1, 0, rng)
        assert p.gold == 3  # turn 1 → 3 gold

    def test_discount_increments(self, player: PlayerState, pool: MinionPool, rng: random.Random) -> None:
        _, _, _, discount = start_recruit_turn(player, None, pool, 1, 2, rng)
        assert discount == 3

    def test_frozen_shop_persists(self, player: PlayerState, pool: MinionPool, rng: random.Random) -> None:
        frozen = ShopState(minion_ids=("T1_A",), frozen=True)
        p, shop, _, _ = start_recruit_turn(player, frozen, pool, 1, 0, rng)
        assert shop.minion_ids == ("T1_A",)
        assert not shop.frozen  # unfreezes

    def test_unfrozen_shop_refreshes(self, player: PlayerState, pool: MinionPool, rng: random.Random) -> None:
        old = ShopState(minion_ids=("T1_A",), frozen=False)
        _, shop, _, _ = start_recruit_turn(player, old, pool, 1, 0, rng)
        assert shop.size == 3  # tier 1 → 3 minions


# ── Buy minion ───────────────────────────────────────────────────────

class TestBuyMinion:
    def test_buy_reduces_gold(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, BuyMinionAction(tavern_index=0), 0, rng)
        assert r.player.gold == player.gold - BUY_COST

    def test_buy_places_on_board(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, BuyMinionAction(tavern_index=0), 0, rng)
        assert len(r.player.board) == 1
        assert r.player.board[0].card_id == "T1_A"

    def test_buy_removes_from_shop(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, BuyMinionAction(tavern_index=0), 0, rng)
        assert "T1_A" not in r.shop.minion_ids

    def test_buy_no_gold_noop(self, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        broke = PlayerState(player_id=0, gold=0)
        r = process_action(broke, shop, pool, BuyMinionAction(tavern_index=0), 0, rng)
        assert r.player.gold == 0
        assert len(r.player.board) == 0

    def test_buy_full_board_goes_to_hand(self, pool: MinionPool, rng: random.Random) -> None:
        # Use distinct card_ids to avoid triggering triple
        board = tuple(
            MinionState(card_id=f"X{i}", attack=1, health=1)
            for i in range(MAX_BOARD)
        )
        player = PlayerState(player_id=0, gold=5, board=board)
        shop = ShopState(minion_ids=("T1_B",))
        r = process_action(player, shop, pool, BuyMinionAction(tavern_index=0), 0, rng)
        assert len(r.player.board) == MAX_BOARD
        assert len(r.player.hand) == 1

    def test_buy_invalid_index_noop(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, BuyMinionAction(tavern_index=99), 0, rng)
        assert r.player.gold == player.gold


# ── Sell minion ──────────────────────────────────────────────────────

class TestSellMinion:
    def test_sell_gives_gold(self, pool: MinionPool, rng: random.Random) -> None:
        m = MinionState(card_id="T1_A", attack=1, health=1)
        player = PlayerState(player_id=0, gold=2, board=(m,))
        r = process_action(player, ShopState(()), pool, SellMinionAction(board_index=0), 0, rng)
        assert r.player.gold == 2 + SELL_VALUE
        assert len(r.player.board) == 0

    def test_sell_returns_to_pool(self, pool: MinionPool, rng: random.Random) -> None:
        m = MinionState(card_id="T1_A", attack=1, health=1)
        player = PlayerState(player_id=0, gold=0, board=(m,))
        before = pool.stock_count("T1_A")
        p2 = pool.take("T1_A")  # simulate it was taken earlier
        r = process_action(player, ShopState(()), p2, SellMinionAction(board_index=0), 0, rng)
        assert r.pool.stock_count("T1_A") == before

    def test_sell_golden_returns_3(self, pool: MinionPool, rng: random.Random) -> None:
        m = MinionState(card_id="T1_A", attack=2, health=2, golden=True)
        player = PlayerState(player_id=0, gold=0, board=(m,))
        p2 = pool.take("T1_A").take("T1_A").take("T1_A")
        r = process_action(player, ShopState(()), p2, SellMinionAction(board_index=0), 0, rng)
        assert r.pool.stock_count("T1_A") == pool.stock_count("T1_A")

    def test_sell_invalid_index_noop(self, pool: MinionPool, rng: random.Random) -> None:
        player = PlayerState(player_id=0, gold=0, board=())
        r = process_action(player, ShopState(()), pool, SellMinionAction(board_index=0), 0, rng)
        assert r.player.gold == 0


class TestSellHandMinion:
    def test_sell_from_hand(self, pool: MinionPool, rng: random.Random) -> None:
        m = MinionState(card_id="T1_A", attack=1, health=1)
        player = PlayerState(player_id=0, gold=0, hand=(m,))
        r = process_action(player, ShopState(()), pool, SellHandMinionAction(hand_index=0), 0, rng)
        assert r.player.gold == SELL_VALUE
        assert len(r.player.hand) == 0


# ── Play minion (hand → board) ───────────────────────────────────────

class TestPlayMinion:
    def test_play_from_hand(self, pool: MinionPool, rng: random.Random) -> None:
        m = MinionState(card_id="T1_A", attack=1, health=1)
        player = PlayerState(player_id=0, gold=0, hand=(m,))
        r = process_action(player, ShopState(()), pool, PlayMinionAction(hand_index=0), 0, rng)
        assert len(r.player.board) == 1
        assert len(r.player.hand) == 0

    def test_play_full_board_noop(self, pool: MinionPool, rng: random.Random) -> None:
        board = tuple(MinionState(card_id="T1_A", attack=1, health=1) for _ in range(MAX_BOARD))
        m = MinionState(card_id="T1_B", attack=2, health=2)
        player = PlayerState(player_id=0, gold=0, board=board, hand=(m,))
        r = process_action(player, ShopState(()), pool, PlayMinionAction(hand_index=0), 0, rng)
        assert len(r.player.hand) == 1  # unchanged


# ── Refresh ──────────────────────────────────────────────────────────

class TestRefreshTavern:
    def test_refresh_costs_1(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, RefreshTavernAction(), 0, rng)
        assert r.player.gold == player.gold - REFRESH_COST

    def test_refresh_changes_shop(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, RefreshTavernAction(), 0, rng)
        # Shop might have same cards by RNG, but let's check it's a valid shop
        assert r.shop.size == 3  # tier 1

    def test_refresh_no_gold_noop(self, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        broke = PlayerState(player_id=0, gold=0)
        r = process_action(broke, shop, pool, RefreshTavernAction(), 0, rng)
        assert r.player.gold == 0


# ── Freeze ───────────────────────────────────────────────────────────

class TestFreezeTavern:
    def test_freeze_toggles(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, FreezeTavernAction(), 0, rng)
        assert r.shop.frozen is True
        r2 = process_action(r.player, r.shop, r.pool, FreezeTavernAction(), 0, rng)
        assert r2.shop.frozen is False

    def test_freeze_keeps_minions(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, FreezeTavernAction(), 0, rng)
        assert r.shop.minion_ids == shop.minion_ids


# ── Upgrade ──────────────────────────────────────────────────────────

class TestUpgradeTavern:
    def test_upgrade_increases_tier(self, pool: MinionPool, rng: random.Random) -> None:
        p = PlayerState(player_id=0, gold=10, tavern_tier=1)
        shop = ShopState(minion_ids=())
        # discount=5 → cost = 6-5 = 1 gold
        r = process_action(p, shop, pool, UpgradeTavernAction(), 5, rng)
        assert r.player.tavern_tier == 2

    def test_upgrade_deducts_gold(self, pool: MinionPool, rng: random.Random) -> None:
        p = PlayerState(player_id=0, gold=10, tavern_tier=1)
        shop = ShopState(minion_ids=())
        r = process_action(p, shop, pool, UpgradeTavernAction(), 4, rng)
        assert r.player.gold == 10 - 2  # cost = 6-4=2

    def test_upgrade_resets_discount(self, pool: MinionPool, rng: random.Random) -> None:
        p = PlayerState(player_id=0, gold=10, tavern_tier=1)
        shop = ShopState(minion_ids=())
        r = process_action(p, shop, pool, UpgradeTavernAction(), 5, rng)
        assert r.upgrade_discount == 0

    def test_upgrade_insufficient_gold_noop(self, pool: MinionPool, rng: random.Random) -> None:
        p = PlayerState(player_id=0, gold=0, tavern_tier=1)
        shop = ShopState(minion_ids=())
        r = process_action(p, shop, pool, UpgradeTavernAction(), 0, rng)
        assert r.player.tavern_tier == 1

    def test_upgrade_max_tier_noop(self, pool: MinionPool, rng: random.Random) -> None:
        p = PlayerState(player_id=0, gold=99, tavern_tier=MAX_TIER)
        shop = ShopState(minion_ids=())
        r = process_action(p, shop, pool, UpgradeTavernAction(), 0, rng)
        assert r.player.tavern_tier == MAX_TIER


# ── End turn ─────────────────────────────────────────────────────────

class TestEndTurn:
    def test_end_sets_flag(self, player: PlayerState, shop: ShopState, pool: MinionPool, rng: random.Random) -> None:
        r = process_action(player, shop, pool, EndTurnAction(), 0, rng)
        assert r.ended is True


# ── Triple merge ─────────────────────────────────────────────────────

class TestTripleMerge:
    def test_three_on_board(self, pool: MinionPool) -> None:
        m = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=1, tavern_tier=1)
        player = PlayerState(player_id=0, board=(m, m, m))
        new_p, _, found, tier = check_triple(player, pool)
        assert found is True
        assert len(new_p.board) == 1
        assert new_p.board[0].golden is True

    def test_golden_stats_doubled_base(self, pool: MinionPool) -> None:
        m = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=1, tavern_tier=1)
        player = PlayerState(player_id=0, board=(m, m, m))
        new_p, _, _, _ = check_triple(player, pool)
        golden = new_p.board[0]
        assert golden.attack == 2  # 3×1 - 1 + 2×1 = 2×base
        assert golden.health == 2

    def test_golden_with_buffs(self, pool: MinionPool) -> None:
        m1 = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=1, tavern_tier=1)
        m2 = MinionState(card_id="T1_A", name="Tabbycat", attack=3, health=1, tavern_tier=1)  # +2 buff
        m3 = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=5, tavern_tier=1)  # +4 buff
        player = PlayerState(player_id=0, board=(m1, m2, m3))
        new_p, _, _, _ = check_triple(player, pool)
        golden = new_p.board[0]
        # golden = Σ(stats) - base: atk = (1+3+1)-1 = 4, hp = (1+1+5)-1 = 6
        assert golden.attack == 4
        assert golden.health == 6

    def test_mixed_board_hand(self, pool: MinionPool) -> None:
        m = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=1, tavern_tier=1)
        player = PlayerState(player_id=0, board=(m,), hand=(m, m))
        new_p, _, found, _ = check_triple(player, pool)
        assert found is True
        # Golden placed on board (was 1 on board minus 1 removed + golden = 1)
        assert len(new_p.board) == 1
        assert new_p.board[0].golden is True
        assert len(new_p.hand) == 0

    def test_no_triple(self, pool: MinionPool) -> None:
        m1 = MinionState(card_id="T1_A", attack=1, health=1)
        m2 = MinionState(card_id="T1_B", attack=2, health=2)
        player = PlayerState(player_id=0, board=(m1, m1, m2))
        _, _, found, _ = check_triple(player, pool)
        assert found is False

    def test_discover_tier(self, pool: MinionPool) -> None:
        m = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=1, tavern_tier=1)
        player = PlayerState(player_id=0, tavern_tier=2, board=(m, m, m))
        _, _, _, discover_tier = check_triple(player, pool)
        assert discover_tier == 3  # tavern_tier + 1

    def test_discover_capped_at_6(self, pool: MinionPool) -> None:
        m = MinionState(card_id="T1_A", name="Tabbycat", attack=1, health=1, tavern_tier=1)
        player = PlayerState(player_id=0, tavern_tier=6, board=(m, m, m))
        _, _, _, discover_tier = check_triple(player, pool)
        assert discover_tier == 6

    def test_golden_ignores_existing_golden(self, pool: MinionPool) -> None:
        m = MinionState(card_id="T1_A", attack=1, health=1)
        g = MinionState(card_id="T1_A", attack=2, health=2, golden=True)
        player = PlayerState(player_id=0, board=(m, m, g))
        _, _, found, _ = check_triple(player, pool)
        assert found is False  # only 2 non-golden

    def test_keywords_merged(self, pool: MinionPool) -> None:
        m1 = MinionState(card_id="T1_A", attack=1, health=1, taunt=True)
        m2 = MinionState(card_id="T1_A", attack=1, health=1, divine_shield=True)
        m3 = MinionState(card_id="T1_A", attack=1, health=1)
        player = PlayerState(player_id=0, board=(m1, m2, m3))
        new_p, _, _, _ = check_triple(player, pool)
        golden = new_p.board[0]
        assert golden.taunt is True
        assert golden.divine_shield is True
