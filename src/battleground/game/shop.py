# -*- coding: utf-8 -*-
"""Shop state and operations for the recruit phase."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .minion_pool import MinionPool

# Minions offered per tavern tier level
SHOP_SIZES: dict[int, int] = {1: 3, 2: 4, 3: 4, 4: 5, 5: 5, 6: 6}


@dataclass(frozen=True)
class ShopState:
    """Current shop offerings for a player."""

    minion_ids: tuple[str, ...]  # card_ids on display
    frozen: bool = False

    @property
    def size(self) -> int:
        return len(self.minion_ids)

    def is_valid_index(self, index: int) -> bool:
        return 0 <= index < len(self.minion_ids)

    def remove_at(self, index: int) -> ShopState:
        """Remove the minion at *index* (after purchase)."""
        ids = list(self.minion_ids)
        ids.pop(index)
        return ShopState(minion_ids=tuple(ids), frozen=self.frozen)

    def toggle_freeze(self) -> ShopState:
        return ShopState(minion_ids=self.minion_ids, frozen=not self.frozen)


def refresh_shop(
    pool: MinionPool,
    tavern_tier: int,
    current_shop: ShopState | None,
    rng: random.Random,
) -> tuple[MinionPool, ShopState]:
    """Return current minions to pool, then draw fresh ones.

    Returns ``(updated_pool, new_shop)``.
    """
    if current_shop is not None:
        for card_id in current_shop.minion_ids:
            pool = pool.return_minion(card_id)

    shop_size = SHOP_SIZES.get(tavern_tier, 6)
    pool, drawn = pool.roll_shop(tavern_tier, shop_size, rng)
    return pool, ShopState(minion_ids=drawn)
