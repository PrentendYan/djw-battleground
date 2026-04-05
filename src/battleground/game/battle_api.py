# -*- coding: utf-8 -*-
"""Unified battle API — converts PlayerState to Firestone format and runs simulation."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from ..types import SimulationResult
from .state import GameState, MinionState, PlayerState

if TYPE_CHECKING:
    from ..bridge.firestone import FirestoneSimulator


class BattleAPI:
    """High-level battle simulation entry point.

    Wraps the Firestone bridge to accept ``PlayerState`` objects directly,
    handling the conversion to/from Firestone's dict format.
    """

    def __init__(self, simulator: FirestoneSimulator) -> None:
        self._sim = simulator

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run_combat(
        self,
        player: PlayerState,
        opponent: PlayerState,
        *,
        num_simulations: int = 10000,
        current_turn: int = 1,
        anomalies: tuple[str, ...] = (),
        valid_tribes: tuple[str, ...] = (),
    ) -> SimulationResult:
        """Run a Monte Carlo combat simulation between two players."""
        battle_info = self._build_battle_info(
            player,
            opponent,
            num_simulations=num_simulations,
            current_turn=current_turn,
            anomalies=anomalies,
            valid_tribes=valid_tribes,
        )
        return self._sim.simulate(battle_info)

    def run_combat_raw(
        self,
        player: PlayerState,
        opponent: PlayerState,
        *,
        num_simulations: int = 10000,
        current_turn: int = 1,
        anomalies: tuple[str, ...] = (),
        valid_tribes: tuple[str, ...] = (),
    ) -> dict:
        """Run simulation and return raw Firestone result dict."""
        battle_info = self._build_battle_info(
            player,
            opponent,
            num_simulations=num_simulations,
            current_turn=current_turn,
            anomalies=anomalies,
            valid_tribes=valid_tribes,
        )
        return self._sim.simulate_raw(battle_info)

    def apply_combat_damage(
        self,
        game: GameState,
        results: dict[tuple[int, int], SimulationResult],
    ) -> GameState:
        """Apply combat results to a GameState, updating health and eliminating players.

        ``results`` maps (player_id, opponent_id) → SimulationResult.
        For simplicity this uses the average damage; for a stochastic game loop
        you'd sample a single outcome instead.
        """
        players = list(game.players)
        for (pid, _oid), result in results.items():
            p_idx = next(i for i, p in enumerate(players) if p.player_id == pid)
            player = players[p_idx]
            if result.loss_rate > result.win_rate:
                # Player lost — takes average loss damage
                dmg = int(round(result.avg_loss_damage))
                if result.losses > 0 and dmg == 0:
                    logger.warning(
                        f"Player {pid} lost {result.loss_rate:.0%} of sims "
                        f"but avg_loss_damage is 0 — possible data issue"
                    )
                    dmg = 1  # Minimum 1 damage to prevent immortal players
                new_armor = max(0, player.armor - dmg)
                remaining_dmg = max(0, dmg - player.armor)
                new_health = player.health - remaining_dmg
                players[p_idx] = replace(
                    player,
                    armor=new_armor,
                    health=new_health,
                )

        # Assign finishing positions to newly dead players
        already_placed = sum(1 for p in players if p.finished_position > 0)
        newly_dead = [i for i, p in enumerate(players) if p.is_dead and p.finished_position == 0]
        # Simultaneous deaths: higher pre-combat health → better placement
        newly_dead.sort(key=lambda i: game.players[i].health, reverse=True)
        for rank_offset, idx in enumerate(newly_dead):
            players[idx] = replace(players[idx], finished_position=8 - already_placed - rank_offset)

        return replace(game, players=tuple(players))

    # ------------------------------------------------------------------
    # Internal: PlayerState → Firestone dict
    # ------------------------------------------------------------------

    @staticmethod
    def _minion_to_entity(m: MinionState, *, friendly: bool = True) -> dict:
        """Convert MinionState to Firestone BoardEntity dict."""
        entity: dict = {
            "entityId": 0,
            "cardId": m.card_id,
            "attack": m.attack,
            "health": m.health,
            "friendly": friendly,
        }
        if m.taunt:
            entity["taunt"] = True
        if m.divine_shield:
            entity["divineShield"] = True
        if m.poisonous:
            entity["poisonous"] = True
        if m.venomous:
            entity["venomous"] = True
        if m.reborn:
            entity["reborn"] = True
        if m.windfury:
            entity["windfury"] = True
        if m.cleave:
            entity["cleave"] = True
        if m.stealth:
            entity["stealth"] = True
        if m.enchantments:
            entity["enchantments"] = list(m.enchantments)
        if m.tavern_tier != 1:
            entity["tavernTier"] = m.tavern_tier
        return entity

    @staticmethod
    def _build_player_board(ps: PlayerState, *, friendly: bool) -> dict:
        """Build Firestone playerBoard/opponentBoard dict from PlayerState."""
        player_dict: dict = {
            "cardId": ps.hero.card_id,
            "hpLeft": ps.health,
            "tavernTier": ps.tavern_tier,
            "heroPowers": list(ps.hero_powers),
            "questEntities": list(ps.quest_entities),
        }
        if ps.global_info:
            player_dict["globalInfo"] = ps.global_info
        if ps.trinkets:
            player_dict["trinkets"] = list(ps.trinkets)
        if ps.hand:
            player_dict["hand"] = [
                BattleAPI._minion_to_entity(m, friendly=friendly)
                for m in ps.hand
            ]

        result: dict = {
            "player": player_dict,
            "board": [
                BattleAPI._minion_to_entity(m, friendly=friendly)
                for m in ps.board
            ],
        }
        if ps.secrets:
            result["secrets"] = list(ps.secrets)
        return result

    @staticmethod
    def _build_battle_info(
        player: PlayerState,
        opponent: PlayerState,
        *,
        num_simulations: int = 10000,
        current_turn: int = 1,
        anomalies: tuple[str, ...] = (),
        valid_tribes: tuple[str, ...] = (),
    ) -> dict:
        """Build complete BgsBattleInfo dict."""
        return {
            "playerBoard": BattleAPI._build_player_board(player, friendly=True),
            "opponentBoard": BattleAPI._build_player_board(opponent, friendly=False),
            "options": {
                "numberOfSimulations": num_simulations,
                "skipInfoLogs": True,
            },
            "gameState": {
                "currentTurn": current_turn,
                "validTribes": list(valid_tribes),
                "anomalies": list(anomalies),
            },
        }
