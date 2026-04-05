# -*- coding: utf-8 -*-
"""Action types for the recruit phase (placeholder for S7).

These types define what a Player can do during the recruit phase.
The actual recruit-phase logic will be implemented in S7.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    """Base action type."""


@dataclass(frozen=True)
class BuyMinionAction(Action):
    """Buy a minion from the tavern at the given index."""
    tavern_index: int


@dataclass(frozen=True)
class SellMinionAction(Action):
    """Sell a minion from the board at the given index."""
    board_index: int


@dataclass(frozen=True)
class RefreshTavernAction(Action):
    """Refresh the tavern offerings (costs 1 gold)."""


@dataclass(frozen=True)
class FreezeTavernAction(Action):
    """Toggle freeze on the current tavern offerings."""


@dataclass(frozen=True)
class UpgradeTavernAction(Action):
    """Upgrade tavern tier."""


@dataclass(frozen=True)
class ReorderBoardAction(Action):
    """Reorder board positions."""
    new_order: tuple[int, ...]  # indices into current board


@dataclass(frozen=True)
class UseHeroPowerAction(Action):
    """Use the hero power."""
    target_index: int | None = None  # Some hero powers need a target


@dataclass(frozen=True)
class PlayMinionAction(Action):
    """Play a minion from hand to board."""
    hand_index: int
    board_position: int = -1  # -1 = append to right


@dataclass(frozen=True)
class SellHandMinionAction(Action):
    """Sell a minion from hand (returns to pool)."""
    hand_index: int


@dataclass(frozen=True)
class EndTurnAction(Action):
    """End the recruit phase."""
