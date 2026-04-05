# -*- coding: utf-8 -*-
"""Recruit phase logic — gold, buy/sell, refresh, upgrade, triple merge.

All functions are pure: they accept immutable state and return new state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from .actions import (
    Action,
    BuyMinionAction,
    EndTurnAction,
    FreezeTavernAction,
    PlayMinionAction,
    RefreshTavernAction,
    SellHandMinionAction,
    SellMinionAction,
    UpgradeTavernAction,
)
from .minion_pool import MinionPool
from .shop import ShopState, refresh_shop
from .state import MinionState, PlayerState

# ── Constants ────────────────────────────────────────────────────────

BUY_COST: int = 3
SELL_VALUE: int = 1
REFRESH_COST: int = 1
UPGRADE_BASE_COSTS: tuple[int, ...] = (6, 7, 8, 9, 10)  # tier 1→2 … 5→6
MAX_BOARD: int = 7
MAX_HAND: int = 10
MAX_TIER: int = 6


# ── Result container ─────────────────────────────────────────────────

@dataclass(frozen=True)
class RecruitResult:
    """Outcome of processing one recruit-phase action."""

    player: PlayerState
    shop: ShopState
    pool: MinionPool
    upgrade_discount: int
    ended: bool = False
    triple_discovered: bool = False
    discover_tier: int = 0  # tier to discover from (tavern_tier + 1)


# ── Pure helpers ─────────────────────────────────────────────────────

def turn_gold(turn: int) -> int:
    """Max gold for turn *turn* (1-indexed). Formula: min(turn + 2, 10)."""
    return min(turn + 2, 10)


def upgrade_cost(tavern_tier: int, discount: int) -> int:
    """Effective upgrade cost for the current tier, after per-turn discount."""
    if tavern_tier >= MAX_TIER:
        return 999
    base = UPGRADE_BASE_COSTS[tavern_tier - 1]
    return max(0, base - discount)


# ── Turn initialisation ─────────────────────────────────────────────

def start_recruit_turn(
    player: PlayerState,
    shop: ShopState | None,
    pool: MinionPool,
    turn: int,
    upgrade_discount: int,
    rng: random.Random,
) -> tuple[PlayerState, ShopState, MinionPool, int]:
    """Set up gold, increment discount, refresh shop (unless frozen).

    Returns ``(player, shop, pool, new_upgrade_discount)``.
    """
    gold = turn_gold(turn)
    player = replace(player, gold=gold, gold_max=gold)
    new_discount = upgrade_discount + 1

    if shop is not None and shop.frozen:
        shop = ShopState(minion_ids=shop.minion_ids, frozen=False)
    else:
        pool, shop = refresh_shop(pool, player.tavern_tier, shop, rng)

    return player, shop, pool, new_discount


# ── Action dispatcher ────────────────────────────────────────────────

def process_action(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    action: Action,
    upgrade_discount: int,
    rng: random.Random,
) -> RecruitResult:
    """Process a single recruit-phase action (pure function)."""
    match action:
        case EndTurnAction():
            return RecruitResult(
                player=player, shop=shop, pool=pool,
                upgrade_discount=upgrade_discount, ended=True,
            )
        case BuyMinionAction(tavern_index=idx):
            return _buy_minion(player, shop, pool, idx, upgrade_discount)
        case SellMinionAction(board_index=idx):
            return _sell_minion(player, shop, pool, idx, upgrade_discount)
        case SellHandMinionAction(hand_index=idx):
            return _sell_hand_minion(player, shop, pool, idx, upgrade_discount)
        case PlayMinionAction(hand_index=hi, board_position=bp):
            return _play_minion(player, shop, pool, hi, bp, upgrade_discount)
        case RefreshTavernAction():
            return _refresh_tavern(player, shop, pool, upgrade_discount, rng)
        case FreezeTavernAction():
            return RecruitResult(
                player=player, shop=shop.toggle_freeze(), pool=pool,
                upgrade_discount=upgrade_discount,
            )
        case UpgradeTavernAction():
            return _upgrade_tavern(player, shop, pool, upgrade_discount)
        case _:
            return RecruitResult(
                player=player, shop=shop, pool=pool,
                upgrade_discount=upgrade_discount,
            )


# ── Individual actions ───────────────────────────────────────────────

def _buy_minion(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    tavern_index: int,
    upgrade_discount: int,
) -> RecruitResult:
    noop = RecruitResult(player=player, shop=shop, pool=pool, upgrade_discount=upgrade_discount)

    if player.gold < BUY_COST:
        return noop
    if not shop.is_valid_index(tavern_index):
        return noop

    total_minions = len(player.board) + len(player.hand)
    if total_minions >= MAX_BOARD + MAX_HAND:
        return noop

    card_id = shop.minion_ids[tavern_index]
    template = pool.get_template(card_id)
    if template is None:
        return noop

    minion = MinionState(
        card_id=template.card_id,
        name=template.name,
        attack=template.attack,
        health=template.health,
        tavern_tier=template.tier,
    )

    # Place on board if space, otherwise hand
    if len(player.board) < MAX_BOARD:
        new_player = replace(
            player,
            gold=player.gold - BUY_COST,
            board=player.board + (minion,),
        )
    else:
        new_player = replace(
            player,
            gold=player.gold - BUY_COST,
            hand=player.hand + (minion,),
        )

    new_shop = shop.remove_at(tavern_index)

    # Triple check
    new_player, new_pool, triple_found, discover_tier = check_triple(new_player, pool)

    return RecruitResult(
        player=new_player, shop=new_shop, pool=new_pool,
        upgrade_discount=upgrade_discount,
        triple_discovered=triple_found,
        discover_tier=discover_tier,
    )


def _sell_minion(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    board_index: int,
    upgrade_discount: int,
) -> RecruitResult:
    noop = RecruitResult(player=player, shop=shop, pool=pool, upgrade_discount=upgrade_discount)

    if board_index < 0 or board_index >= len(player.board):
        return noop

    sold = player.board[board_index]
    new_board = player.board[:board_index] + player.board[board_index + 1:]
    new_player = replace(player, gold=player.gold + SELL_VALUE, board=new_board)

    # Golden → return 3 copies; normal → 1
    copies = 3 if sold.golden else 1
    for _ in range(copies):
        pool = pool.return_minion(sold.card_id)

    return RecruitResult(
        player=new_player, shop=shop, pool=pool,
        upgrade_discount=upgrade_discount,
    )


def _sell_hand_minion(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    hand_index: int,
    upgrade_discount: int,
) -> RecruitResult:
    noop = RecruitResult(player=player, shop=shop, pool=pool, upgrade_discount=upgrade_discount)

    if hand_index < 0 or hand_index >= len(player.hand):
        return noop

    sold = player.hand[hand_index]
    new_hand = player.hand[:hand_index] + player.hand[hand_index + 1:]
    new_player = replace(player, gold=player.gold + SELL_VALUE, hand=new_hand)

    copies = 3 if sold.golden else 1
    for _ in range(copies):
        pool = pool.return_minion(sold.card_id)

    return RecruitResult(
        player=new_player, shop=shop, pool=pool,
        upgrade_discount=upgrade_discount,
    )


def _play_minion(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    hand_index: int,
    board_position: int,
    upgrade_discount: int,
) -> RecruitResult:
    noop = RecruitResult(player=player, shop=shop, pool=pool, upgrade_discount=upgrade_discount)

    if hand_index < 0 or hand_index >= len(player.hand):
        return noop
    if len(player.board) >= MAX_BOARD:
        return noop

    minion = player.hand[hand_index]
    new_hand = player.hand[:hand_index] + player.hand[hand_index + 1:]
    board = list(player.board)
    if board_position < 0 or board_position >= len(board):
        board.append(minion)
    else:
        board.insert(board_position, minion)
    new_player = replace(player, board=tuple(board), hand=new_hand)

    return RecruitResult(
        player=new_player, shop=shop, pool=pool,
        upgrade_discount=upgrade_discount,
    )


def _refresh_tavern(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    upgrade_discount: int,
    rng: random.Random,
) -> RecruitResult:
    if player.gold < REFRESH_COST:
        return RecruitResult(
            player=player, shop=shop, pool=pool,
            upgrade_discount=upgrade_discount,
        )
    new_player = replace(player, gold=player.gold - REFRESH_COST)
    pool, new_shop = refresh_shop(pool, new_player.tavern_tier, shop, rng)
    return RecruitResult(
        player=new_player, shop=new_shop, pool=pool,
        upgrade_discount=upgrade_discount,
    )


def _upgrade_tavern(
    player: PlayerState,
    shop: ShopState,
    pool: MinionPool,
    upgrade_discount: int,
) -> RecruitResult:
    noop = RecruitResult(player=player, shop=shop, pool=pool, upgrade_discount=upgrade_discount)

    if player.tavern_tier >= MAX_TIER:
        return noop
    cost = upgrade_cost(player.tavern_tier, upgrade_discount)
    if player.gold < cost:
        return noop

    new_player = replace(
        player,
        gold=player.gold - cost,
        tavern_tier=player.tavern_tier + 1,
    )
    return RecruitResult(
        player=new_player, shop=shop, pool=pool,
        upgrade_discount=0,  # reset after upgrade
    )


# ── Triple merge ─────────────────────────────────────────────────────

def check_triple(
    player: PlayerState,
    pool: MinionPool,
) -> tuple[PlayerState, MinionPool, bool, int]:
    """Scan hand + board for three non-golden copies; merge first found.

    Golden stats = 2 × base + sum-of-buffs from all three copies.
    Returns ``(player, pool, triple_found, discover_tier)``.
    """
    # Index all non-golden minions by card_id
    entries: dict[str, list[tuple[str, int]]] = {}  # card_id → [(location, idx)]
    for i, m in enumerate(player.board):
        if not m.golden:
            entries.setdefault(m.card_id, []).append(("board", i))
    for i, m in enumerate(player.hand):
        if not m.golden:
            entries.setdefault(m.card_id, []).append(("hand", i))

    for card_id, locs in entries.items():
        if len(locs) < 3:
            continue

        three_locs = locs[:3]
        template = pool.get_template(card_id)
        base_atk = template.attack if template else 0
        base_hp = template.health if template else 0

        # Gather the three MinionState objects
        minions: list[MinionState] = []
        for loc, idx in three_locs:
            m = player.board[idx] if loc == "board" else player.hand[idx]
            minions.append(m)

        # Golden formula: 2×base + Σ(buffs) = Σ(stats) − base
        golden_atk = sum(m.attack for m in minions) - base_atk
        golden_hp = sum(m.health for m in minions) - base_hp
        golden = MinionState(
            card_id=card_id,
            name=minions[0].name,
            attack=golden_atk,
            health=golden_hp,
            tavern_tier=minions[0].tavern_tier,
            golden=True,
            taunt=any(m.taunt for m in minions),
            divine_shield=any(m.divine_shield for m in minions),
            poisonous=any(m.poisonous for m in minions),
            venomous=any(m.venomous for m in minions),
            reborn=any(m.reborn for m in minions),
            windfury=any(m.windfury for m in minions),
            cleave=any(m.cleave for m in minions),
            stealth=any(m.stealth for m in minions),
        )

        # Remove three copies (reverse-sorted indices to keep earlier ones valid)
        board = list(player.board)
        hand = list(player.hand)
        board_rm = sorted([idx for loc, idx in three_locs if loc == "board"], reverse=True)
        hand_rm = sorted([idx for loc, idx in three_locs if loc == "hand"], reverse=True)
        for idx in board_rm:
            board.pop(idx)
        for idx in hand_rm:
            hand.pop(idx)

        # Place golden on board if space, else hand
        if len(board) < MAX_BOARD:
            board.append(golden)
        elif len(hand) < MAX_HAND:
            hand.append(golden)

        new_player = replace(player, board=tuple(board), hand=tuple(hand))
        discover_tier = min(player.tavern_tier + 1, MAX_TIER)
        return new_player, pool, True, discover_tier

    return player, pool, False, 0
