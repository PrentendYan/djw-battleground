# -*- coding: utf-8 -*-
"""Board state management — 7-slot minion board with targeting logic."""

from __future__ import annotations

import random as _random
from typing import TYPE_CHECKING

from .minion import Minion

if TYPE_CHECKING:
    pass


class Board:
    """Manages one side's board of up to 7 minions."""

    MAX_SIZE = 7

    def __init__(self, minions: list[Minion] | None = None) -> None:
        self._minions: list[Minion] = list(minions) if minions else []
        self._next_attacker_idx: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def minions(self) -> list[Minion]:
        return self._minions

    @property
    def is_empty(self) -> bool:
        return len(self._minions) == 0

    @property
    def is_full(self) -> bool:
        return len(self._minions) >= self.MAX_SIZE

    def __len__(self) -> int:
        return len(self._minions)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, minion: Minion, position: int | None = None) -> bool:
        """Insert minion at position (or append). Returns False if board full."""
        if self.is_full:
            return False
        if position is None or position >= len(self._minions):
            self._minions.append(minion)
        else:
            position = max(0, position)
            self._minions.insert(position, minion)
            # Shift attacker pointer if insertion is before it
            if position <= self._next_attacker_idx and len(self._minions) > 1:
                self._next_attacker_idx += 1
        return True

    def remove(self, minion: Minion) -> int:
        """Remove minion from board. Returns its former position.

        Adjusts the attacker pointer so the next attacker is correct.
        """
        idx = self._minions.index(minion)
        self._minions.pop(idx)

        if not self._minions:
            self._next_attacker_idx = 0
        elif idx < self._next_attacker_idx:
            self._next_attacker_idx -= 1
        # If idx == _next_attacker_idx, pointer now points at the minion
        # that slid into the removed slot — correct behavior (it's "next").
        if self._minions and self._next_attacker_idx >= len(self._minions):
            self._next_attacker_idx = 0

        return idx

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_next_attacker(self) -> Minion | None:
        """Return next minion that can attack (attack > 0), advancing pointer.

        Scans up to one full cycle. Returns None if no minion can attack.
        """
        if self.is_empty:
            return None

        n = len(self._minions)
        start = self._next_attacker_idx
        for i in range(n):
            idx = (start + i) % n
            minion = self._minions[idx]
            if minion.attack > 0:
                self._next_attacker_idx = (idx + 1) % n
                return minion
        return None  # All 0-attack

    def get_random_target(
        self,
        *,
        exclude_stealth: bool = True,
        rng: _random.Random | None = None,
    ) -> Minion | None:
        """Pick a random attack target. Taunts have priority."""
        if self.is_empty:
            return None

        rand = rng or _random

        # Filter valid targets
        if exclude_stealth:
            valid = [m for m in self._minions if not m.stealth]
        else:
            valid = list(self._minions)

        if not valid:
            # All stealthed — shouldn't happen but be safe
            valid = list(self._minions)

        # Taunt check
        taunts = [m for m in valid if m.taunt]
        pool = taunts if taunts else valid

        return rand.choice(pool)

    def get_adjacent(self, minion: Minion) -> tuple[Minion | None, Minion | None]:
        """Return (left_neighbor, right_neighbor) of a minion."""
        idx = self._minions.index(minion)
        left = self._minions[idx - 1] if idx > 0 else None
        right = self._minions[idx + 1] if idx < len(self._minions) - 1 else None
        return left, right

    def get_position(self, minion: Minion) -> int:
        return self._minions.index(minion)

    def has_tribe(self, tribe: "Tribe") -> bool:  # noqa: F821
        from .types import Tribe

        return any(tribe in m.tribes or Tribe.ALL in m.tribes for m in self._minions)

    # ------------------------------------------------------------------
    # Copy
    # ------------------------------------------------------------------

    def clone(self) -> Board:
        """Deep copy for Monte Carlo simulation."""
        new = Board()
        new._minions = [m.clone() for m in self._minions]
        new._next_attacker_idx = self._next_attacker_idx
        return new

    def __repr__(self) -> str:
        return f"Board({', '.join(repr(m) for m in self._minions)})"
