# -*- coding: utf-8 -*-
"""Core game state types for Battlegrounds simulation.

All state types are frozen dataclasses — mutation produces new instances
via dataclasses.replace().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class GamePhase(Enum):
    """Current phase of a BG round."""

    RECRUIT = auto()
    COMBAT = auto()


@dataclass(frozen=True)
class MinionState:
    """Serialisable snapshot of a single board minion.

    Unlike ``minion.Minion`` (mutable, has hook methods), this is a pure-data
    record used to describe a board position before simulation.
    """

    card_id: str
    attack: int
    health: int
    tavern_tier: int = 1

    # Keywords
    taunt: bool = False
    divine_shield: bool = False
    poisonous: bool = False
    venomous: bool = False
    reborn: bool = False
    windfury: bool = False
    cleave: bool = False
    stealth: bool = False
    golden: bool = False

    # Optional display info (not used by engine)
    name: str = ""
    enchantments: tuple[dict, ...] = ()


@dataclass(frozen=True)
class HeroState:
    """Hero identity and hero-power state."""

    card_id: str = "TB_BaconShop_HERO_01"  # Default: Bartender Bob
    hero_power_card_id: str = ""
    hero_power_used: bool = False


@dataclass(frozen=True)
class PlayerState:
    """Full state of a single BG player."""

    player_id: int
    health: int = 40
    armor: int = 0
    tavern_tier: int = 1
    gold: int = 0
    gold_max: int = 3

    hero: HeroState = field(default_factory=HeroState)
    board: tuple[MinionState, ...] = ()
    hand: tuple[MinionState, ...] = ()

    # S6 fields — populated when game mechanics are complete
    # NOTE: inner dicts are mutable (Firestone pass-through); callers must not mutate
    hero_powers: tuple[dict[str, Any], ...] = ()
    secrets: tuple[dict[str, Any], ...] = ()
    trinkets: tuple[dict[str, Any], ...] = ()
    quest_entities: tuple[dict[str, Any], ...] = ()
    global_info: dict[str, Any] | None = None

    # Tracking
    finished_position: int = 0  # 1-8 when eliminated

    @property
    def alive(self) -> bool:
        return self.health > 0

    @property
    def is_dead(self) -> bool:
        return self.health <= 0

    @property
    def effective_health(self) -> int:
        return self.health + self.armor


@dataclass(frozen=True)
class GameState:
    """State of an entire BG lobby (8 players)."""

    players: tuple[PlayerState, ...] = ()
    current_turn: int = 1
    phase: GamePhase = GamePhase.RECRUIT

    # Lobby-wide
    anomalies: tuple[str, ...] = ()
    valid_tribes: tuple[str, ...] = ()

    # Matchmaking history: player_id → recent opponent ids (immutable)
    pairing_history: tuple[tuple[int, tuple[int, ...]], ...] = ()

    @property
    def alive_players(self) -> tuple[PlayerState, ...]:
        return tuple(p for p in self.players if p.alive)

    @property
    def num_alive(self) -> int:
        return len(self.alive_players)

    @property
    def is_game_over(self) -> bool:
        return self.num_alive <= 1

    def get_player(self, player_id: int) -> PlayerState | None:
        for p in self.players:
            if p.player_id == player_id:
                return p
        return None

    def get_recent_opponents(self, player_id: int) -> tuple[int, ...]:
        """Get recent opponent IDs for a player from pairing history."""
        for pid, opps in self.pairing_history:
            if pid == player_id:
                return opps
        return ()
