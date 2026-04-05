# -*- coding: utf-8 -*-
"""Core type definitions for Battlegrounds simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Tribe(Enum):
    """Minion tribe types."""

    BEAST = auto()
    DEMON = auto()
    DRAGON = auto()
    ELEMENTAL = auto()
    MECH = auto()
    MURLOC = auto()
    NAGA = auto()
    PIRATE = auto()
    QUILBOAR = auto()
    UNDEAD = auto()
    ALL = auto()  # Amalgam-type minions


class CombatResult(Enum):
    """Outcome of a single combat."""

    WIN = auto()  # Player 0 wins
    LOSS = auto()  # Player 1 wins
    DRAW = auto()


@dataclass(frozen=True)
class CombatOutcome:
    """Full result of a single combat simulation."""

    result: CombatResult
    damage: int  # Damage dealt by the winner (0 for draw)
    winning_side: int  # 0 or 1; -1 for draw


@dataclass
class SimulationResult:
    """Aggregated results from Monte Carlo simulation."""

    wins: int = 0
    losses: int = 0
    ties: int = 0
    total: int = 0

    win_damages: list[int] = field(default_factory=list)
    loss_damages: list[int] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.total if self.total else 0.0

    @property
    def loss_rate(self) -> float:
        return self.losses / self.total if self.total else 0.0

    @property
    def tie_rate(self) -> float:
        return self.ties / self.total if self.total else 0.0

    # Firestone pre-computed values (set by bridge, not by our engine)
    _firestone_avg_win_dmg: float = 0.0
    _firestone_avg_loss_dmg: float = 0.0
    _firestone_lethal_win: float = 0.0
    _firestone_lethal_loss: float = 0.0

    @property
    def avg_win_damage(self) -> float:
        if self.win_damages:
            return sum(self.win_damages) / len(self.win_damages)
        return self._firestone_avg_win_dmg

    @property
    def avg_loss_damage(self) -> float:
        if self.loss_damages:
            return sum(self.loss_damages) / len(self.loss_damages)
        return self._firestone_avg_loss_dmg

    def summary(self) -> str:
        return (
            f"Win: {self.win_rate:.1%} | Tie: {self.tie_rate:.1%} | Loss: {self.loss_rate:.1%}\n"
            f"Avg win dmg: {self.avg_win_damage:.1f} | Avg loss dmg: {self.avg_loss_damage:.1f}\n"
            f"({self.total} simulations)"
        )
