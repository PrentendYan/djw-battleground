# -*- coding: utf-8 -*-
"""Minion pool — finite shared pool of BG minion copies.

Each BG minion card has a limited number of copies based on its tier.
When bought, one copy leaves the pool; when sold, it returns.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class MinionTemplate:
    """Base stats of a BG pool minion."""

    card_id: str
    name: str
    attack: int
    health: int
    tier: int


@dataclass(frozen=True)
class MinionPool:
    """Shared minion pool with finite copies per card.

    ``stock`` and ``templates`` are plain dicts treated as immutable
    by convention (same pattern as PlayerState.global_info).
    Every mutating operation returns a **new** MinionPool.
    """

    TIER_COPIES: ClassVar[dict[int, int]] = {
        1: 16, 2: 15, 3: 13, 4: 11, 5: 9, 6: 7,
    }

    stock: dict[str, int]
    templates: dict[str, MinionTemplate]

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_cards(cls, cards: list[dict]) -> MinionPool:
        """Initialise pool from ``cards_cache.json`` card dicts."""
        templates: dict[str, MinionTemplate] = {}
        stock: dict[str, int] = {}
        for card in cards:
            if not card.get("isBaconPool"):
                continue
            if card.get("type") != "Minion":
                continue
            card_id: str = card["id"]
            tier: int = card.get("techLevel", 1)
            templates[card_id] = MinionTemplate(
                card_id=card_id,
                name=card.get("name", card_id),
                attack=card.get("attack", 0),
                health=card.get("health", 0),
                tier=tier,
            )
            stock[card_id] = cls.TIER_COPIES.get(tier, 0)
        return cls(stock=dict(stock), templates=dict(templates))

    @classmethod
    def from_templates(cls, templates: dict[str, MinionTemplate]) -> MinionPool:
        """Initialise pool from pre-built templates (handy for tests)."""
        stock = {
            cid: cls.TIER_COPIES.get(t.tier, 0)
            for cid, t in templates.items()
        }
        return cls(stock=dict(stock), templates=dict(templates))

    # ------------------------------------------------------------------
    # Pool operations (all return new MinionPool)
    # ------------------------------------------------------------------

    def take(self, card_id: str) -> MinionPool:
        """Remove one copy from the pool."""
        count = self.stock.get(card_id, 0)
        if count <= 0:
            raise ValueError(f"No copies of {card_id} left in pool")
        new_stock = dict(self.stock)
        new_stock[card_id] = count - 1
        return MinionPool(stock=new_stock, templates=self.templates)

    def return_minion(self, card_id: str) -> MinionPool:
        """Return one copy to the pool (capped at tier max)."""
        if card_id not in self.templates:
            return self  # generated / golden-only minions — nothing to return
        max_copies = self.TIER_COPIES.get(self.templates[card_id].tier, 0)
        new_stock = dict(self.stock)
        current = new_stock.get(card_id, 0)
        new_stock[card_id] = min(current + 1, max_copies)
        return MinionPool(stock=new_stock, templates=self.templates)

    def available_by_tier(self, max_tier: int) -> list[str]:
        """Card-ids with ``tier <= max_tier`` and at least one copy left."""
        return [
            cid
            for cid, count in self.stock.items()
            if count > 0 and self.templates[cid].tier <= max_tier
        ]

    def roll_shop(
        self,
        tavern_tier: int,
        count: int,
        rng: random.Random,
    ) -> tuple[MinionPool, tuple[str, ...]]:
        """Draw *count* weighted-random minions (tier ≤ tavern_tier).

        More remaining copies → higher draw chance (standard BG behaviour).
        Returns ``(updated_pool, drawn_card_ids)``.
        """
        pool = self
        drawn: list[str] = []
        for _ in range(count):
            available = pool.available_by_tier(tavern_tier)
            if not available:
                break
            weights = [pool.stock[cid] for cid in available]
            choice = rng.choices(available, weights=weights, k=1)[0]
            drawn.append(choice)
            pool = pool.take(choice)
        return pool, tuple(drawn)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_template(self, card_id: str) -> MinionTemplate | None:
        return self.templates.get(card_id)

    def stock_count(self, card_id: str) -> int:
        return self.stock.get(card_id, 0)
