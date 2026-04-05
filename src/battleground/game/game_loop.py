# -*- coding: utf-8 -*-
"""Full BG game loop: recruit → matchmake → combat → damage → eliminate.

The loop supports two combat modes:

* **Firestone** — uses ``BattleAPI`` + Node.js engine (accurate).
* **Simple** — coin-flip combat with tier-based damage (no Node dependency;
  useful for fast iteration and testing).
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, replace
from typing import Protocol

from .actions import (
    BuyMinionAction,
    PlayMinionAction,
    RefreshTavernAction,
    SellHandMinionAction,
    SellMinionAction,
    UpgradeTavernAction,
)
from .matchmaking import Matchmaker
from .minion_pool import MinionPool
from .recruit import (
    process_action,
    start_recruit_turn,
)
from .shop import ShopState
from .state import GameState, MinionState, PlayerState

logger = logging.getLogger(__name__)

# ── Damage helpers ───────────────────────────────────────────────────

EARLY_TURN_CAP = 8
EARLY_DAMAGE_CAP = 15


def calculate_damage(
    winner_tavern_tier: int,
    surviving_board: tuple[MinionState, ...],
    turn: int,
) -> int:
    """Damage = hero tavern tier + Σ surviving minion tiers (capped before turn 8)."""
    total = winner_tavern_tier + sum(m.tavern_tier for m in surviving_board)
    if turn < EARLY_TURN_CAP and total > EARLY_DAMAGE_CAP:
        total = EARLY_DAMAGE_CAP
    return total


# ── Player protocol (extended for game loop) ─────────────────────────

class GamePlayer(Protocol):
    """Minimum interface the game loop requires from a player agent."""

    @property
    def player_id(self) -> int: ...

    def choose_action(
        self,
        own_state: PlayerState,
        game: GameState,
        *,
        shop_size: int = 0,
        upgrade_discount: int = 0,
    ) -> ...: ...


# ── Game Loop ────────────────────────────────────────────────────────

MAX_ACTIONS_PER_TURN = 30  # safety limit to prevent infinite loops


@dataclass(frozen=True)
class PlayerTurnLog:
    """What one player did during a single recruit + combat turn."""

    player_id: int
    turn: int
    # Recruit
    gold_given: int = 0
    gold_spent: int = 0
    shop_offered: tuple[str, ...] = ()  # card names in shop
    actions: tuple[str, ...] = ()  # human-readable action list
    bought: int = 0
    sold: int = 0
    upgraded: bool = False
    triple: bool = False
    tier_after: int = 1
    board_after: int = 0
    hand_after: int = 0
    # Combat
    opponent_id: int | None = None
    combat_result: str = ""  # "won N dmg" / "lost N dmg" / "tie"


@dataclass(frozen=True)
class TurnLog:
    """Aggregate log for one turn."""

    turn: int
    player_logs: tuple[PlayerTurnLog, ...] = ()


class GameLoop:
    """Orchestrates a complete BG game for 8 (or fewer) players.

    Usage::

        from battleground.game.random_player import RandomPlayer
        players = [RandomPlayer(i) for i in range(8)]
        pool = MinionPool.from_cards(cards)
        loop = GameLoop(players, pool)
        final = loop.run()
    """

    def __init__(
        self,
        players: list[GamePlayer],
        pool: MinionPool,
        *,
        battle_api: object | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._players: dict[int, GamePlayer] = {p.player_id: p for p in players}
        self._pool = pool
        self._battle_api = battle_api
        self._rng = rng or random.Random()
        self._matchmaker = Matchmaker()

        # Per-player mutable tracking (not part of frozen GameState)
        self._shops: dict[int, ShopState | None] = {p.player_id: None for p in players}
        self._upgrade_discounts: dict[int, int] = {p.player_id: 0 for p in players}
        self._turn_logs: dict[int, TurnLog] = {}

        # Build initial GameState
        player_states = tuple(
            PlayerState(player_id=p.player_id, health=40, tavern_tier=1)
            for p in players
        )
        self._game = GameState(players=player_states, current_turn=0)

    @property
    def game(self) -> GameState:
        return self._game

    @property
    def turn_logs(self) -> dict[int, TurnLog]:
        return self._turn_logs

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, *, max_turns: int = 40) -> GameState:
        """Run the full game until one player remains or *max_turns* reached."""
        for _ in range(max_turns):
            self.step()
            if self._game.is_game_over:
                break
        return self._game

    def step(self) -> GameState:
        """Run a single turn (recruit + combat). Returns updated state."""
        if self._game.is_game_over:
            return self._game
        turn = self._game.current_turn + 1
        self._game = replace(self._game, current_turn=turn)
        logger.info(f"=== Turn {turn} | {self._game.num_alive} alive ===")
        self._recruit_phase(turn)
        self._combat_phase(turn)
        return self._game

    # ------------------------------------------------------------------
    # Recruit
    # ------------------------------------------------------------------

    def _recruit_phase(self, turn: int) -> None:
        players = list(self._game.players)
        player_logs: list[PlayerTurnLog] = []

        for i, ps in enumerate(players):
            if ps.is_dead:
                continue

            agent = self._players.get(ps.player_id)
            if agent is None:
                continue

            ps, shop, self._pool, discount = start_recruit_turn(
                ps,
                self._shops.get(ps.player_id),
                self._pool,
                turn,
                self._upgrade_discounts.get(ps.player_id, 0),
                self._rng,
            )
            self._upgrade_discounts[ps.player_id] = discount

            gold_start = ps.gold
            shop_names = tuple(
                (self._pool.get_template(cid).name if self._pool.get_template(cid) else cid)
                for cid in shop.minion_ids
            )
            action_strs: list[str] = []
            bought = 0
            sold = 0
            upgraded = False
            triple = False

            # Let agent choose actions until EndTurn or safety cap
            for _ in range(MAX_ACTIONS_PER_TURN):
                action = agent.choose_action(
                    ps,
                    self._game,
                    shop_size=shop.size,
                    upgrade_discount=discount,
                )
                result = process_action(ps, shop, self._pool, action, discount, self._rng)

                # Log the action
                match action:
                    case BuyMinionAction(tavern_index=idx):
                        if result.player.gold < ps.gold:
                            name = (self._pool.get_template(shop.minion_ids[idx]).name
                                    if shop.is_valid_index(idx) and self._pool.get_template(shop.minion_ids[idx])
                                    else "?")
                            action_strs.append(f"Buy {name}")
                            bought += 1
                    case SellMinionAction(board_index=idx):
                        if result.player.gold > ps.gold:
                            name = ps.board[idx].name or ps.board[idx].card_id if idx < len(ps.board) else "?"
                            action_strs.append(f"Sell {name}")
                            sold += 1
                    case SellHandMinionAction(hand_index=idx):
                        if result.player.gold > ps.gold:
                            action_strs.append("Sell (hand)")
                            sold += 1
                    case RefreshTavernAction():
                        if result.player.gold < ps.gold:
                            action_strs.append("Refresh")
                    case UpgradeTavernAction():
                        if result.player.tavern_tier > ps.tavern_tier:
                            action_strs.append(f"Upgrade -> T{result.player.tavern_tier}")
                            upgraded = True

                if result.triple_discovered:
                    action_strs.append(f"Triple! Discover T{result.discover_tier}")
                    triple = True

                ps = result.player
                shop = result.shop
                self._pool = result.pool
                discount = result.upgrade_discount

                if result.ended:
                    break

            self._shops[ps.player_id] = shop
            self._upgrade_discounts[ps.player_id] = discount
            players[i] = ps

            player_logs.append(PlayerTurnLog(
                player_id=ps.player_id,
                turn=turn,
                gold_given=gold_start,
                gold_spent=gold_start - ps.gold,
                shop_offered=shop_names,
                actions=tuple(action_strs),
                bought=bought,
                sold=sold,
                upgraded=upgraded,
                triple=triple,
                tier_after=ps.tavern_tier,
                board_after=len(ps.board),
                hand_after=len(ps.hand),
            ))

        self._turn_logs[turn] = TurnLog(turn=turn, player_logs=tuple(player_logs))
        self._game = replace(self._game, players=tuple(players))

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------

    def _combat_phase(self, turn: int) -> None:
        pairs = self._matchmaker.pair(self._game, self._rng)
        self._game = self._matchmaker.update_history(self._game, pairs)

        players = list(self._game.players)

        # Map pid → combat result for log enrichment
        combat_info: dict[int, tuple[int | None, str]] = {}  # pid → (opp_id, result_str)

        for p1, p2 in pairs:
            p1_idx = next(i for i, p in enumerate(players) if p.player_id == p1.player_id)
            p2_idx = next(
                (i for i, p in enumerate(players) if p.player_id == p2.player_id),
                None,
            )

            p1_current = players[p1_idx]
            p2_current = players[p2_idx] if p2_idx is not None else p2

            winner_pid, damage = self._resolve_combat(p1_current, p2_current, turn)

            if winner_pid == p1_current.player_id:
                if p2_idx is not None:
                    players[p2_idx] = _apply_damage(players[p2_idx], damage)
                combat_info[p1_current.player_id] = (p2_current.player_id, f"Won, dealt {damage}")
                combat_info[p2_current.player_id] = (p1_current.player_id, f"Lost, took {damage}")
            elif winner_pid == p2_current.player_id:
                players[p1_idx] = _apply_damage(players[p1_idx], damage)
                combat_info[p1_current.player_id] = (p2_current.player_id, f"Lost, took {damage}")
                combat_info[p2_current.player_id] = (p1_current.player_id, f"Won, dealt {damage}")
            else:
                combat_info[p1_current.player_id] = (p2_current.player_id, "Tie")
                combat_info[p2_current.player_id] = (p1_current.player_id, "Tie")

        # Enrich turn logs with combat info
        if turn in self._turn_logs:
            enriched = []
            for plog in self._turn_logs[turn].player_logs:
                opp_id, result_str = combat_info.get(plog.player_id, (None, ""))
                enriched.append(replace(plog, opponent_id=opp_id, combat_result=result_str))
            self._turn_logs[turn] = TurnLog(turn=turn, player_logs=tuple(enriched))

        # Assign finishing positions to newly dead
        already_placed = sum(1 for p in players if p.finished_position > 0)
        newly_dead = [i for i, p in enumerate(players) if p.is_dead and p.finished_position == 0]
        newly_dead.sort(key=lambda i: self._game.players[i].health, reverse=True)
        for rank_offset, idx in enumerate(newly_dead):
            players[idx] = replace(
                players[idx],
                finished_position=len(self._game.players) - already_placed - rank_offset,
            )

        self._game = replace(self._game, players=tuple(players))

    def _resolve_combat(
        self,
        p1: PlayerState,
        p2: PlayerState,
        turn: int,
    ) -> tuple[int | None, int]:
        """Resolve combat between two players.

        If ``battle_api`` was provided, delegates to Firestone.
        Otherwise uses a simple heuristic (total-stats coin flip).

        Returns ``(winner_player_id_or_None, damage)``.
        """
        if self._battle_api is not None:
            return self._resolve_firestone(p1, p2, turn)
        return self._resolve_simple(p1, p2, turn)

    def _resolve_firestone(
        self,
        p1: PlayerState,
        p2: PlayerState,
        turn: int,
    ) -> tuple[int | None, int]:
        """Use BattleAPI / Firestone for combat resolution."""
        from .battle_api import BattleAPI

        api: BattleAPI = self._battle_api  # type: ignore[assignment]
        result = api.run_combat(p1, p2, num_simulations=1, current_turn=turn)

        if result.win_rate > result.loss_rate:
            dmg = max(1, int(round(result.avg_win_damage)))
            dmg = _cap_damage(dmg, turn)
            return p1.player_id, dmg
        elif result.loss_rate > result.win_rate:
            dmg = max(1, int(round(result.avg_loss_damage)))
            dmg = _cap_damage(dmg, turn)
            return p2.player_id, dmg
        return None, 0

    def _resolve_simple(
        self,
        p1: PlayerState,
        p2: PlayerState,
        turn: int,
    ) -> tuple[int | None, int]:
        """Simple heuristic combat: total stats comparison + randomness."""
        def total_stats(ps: PlayerState) -> int:
            return sum(m.attack + m.health for m in ps.board)

        s1, s2 = total_stats(p1), total_stats(p2)
        if s1 == 0 and s2 == 0:
            return None, 0

        # Win probability proportional to total stats
        total = s1 + s2
        if self._rng.random() < s1 / total:
            dmg = calculate_damage(p1.tavern_tier, p1.board, turn)
            return p1.player_id, dmg
        else:
            dmg = calculate_damage(p2.tavern_tier, p2.board, turn)
            return p2.player_id, dmg


# ── Module-level helpers ─────────────────────────────────────────────

def _apply_damage(player: PlayerState, damage: int) -> PlayerState:
    """Apply damage to armor first, then health."""
    new_armor = max(0, player.armor - damage)
    remaining = max(0, damage - player.armor)
    return replace(player, armor=new_armor, health=player.health - remaining)


def _cap_damage(damage: int, turn: int) -> int:
    if turn < EARLY_TURN_CAP and damage > EARLY_DAMAGE_CAP:
        return EARLY_DAMAGE_CAP
    return damage
