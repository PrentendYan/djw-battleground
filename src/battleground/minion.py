# -*- coding: utf-8 -*-
"""Minion data model with keyword attributes and hook methods."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from .types import Tribe

if TYPE_CHECKING:
    from .combat import CombatContext


class Minion:
    """Base minion class.

    Subclasses override hook methods (on_*, deathrattle) to implement
    specific minion effects. The combat engine calls these hooks at the
    appropriate points during combat resolution.
    """

    def __init__(
        self,
        card_id: str = "",
        name: str = "",
        attack: int = 0,
        health: int = 0,
        tier: int = 1,
        tribes: list[Tribe] | None = None,
        *,
        taunt: bool = False,
        divine_shield: bool = False,
        poisonous: bool = False,
        venomous: bool = False,
        windfury: bool = False,
        mega_windfury: bool = False,
        reborn: bool = False,
        cleave: bool = False,
        stealth: bool = False,
        golden: bool = False,
    ) -> None:
        self.card_id = card_id
        self.name = name
        self.attack = attack
        self.health = health
        self.tier = tier
        self.tribes = tribes or []

        # Keywords
        self.taunt = taunt
        self.divine_shield = divine_shield
        self.poisonous = poisonous
        self.venomous = venomous
        self.windfury = windfury
        self.mega_windfury = mega_windfury
        self.reborn = reborn
        self.cleave = cleave
        self.stealth = stealth
        self.golden = golden

        # Internal state — set by CombatEngine
        self._entry_order: int = 0
        self._reborn_triggered: bool = False

        # Avenge
        self._avenge_threshold: int = 0
        self._avenge_counter: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_alive(self) -> bool:
        return self.health > 0

    @property
    def num_attacks(self) -> int:
        """Number of attacks per turn (Windfury/Mega-Windfury)."""
        if self.mega_windfury:
            return 4
        if self.windfury:
            return 2
        return 1

    @property
    def deathrattle_multiplier(self) -> int:
        """Override in Baron Rivendare to return 2 (golden: 3)."""
        return 1

    # ------------------------------------------------------------------
    # Hook methods — override in subclasses
    # ------------------------------------------------------------------

    def on_start_of_combat(self, ctx: CombatContext) -> None:
        """Fires once at the very start of combat, before any attacks."""

    def on_pre_attack(self, target: Minion, ctx: CombatContext) -> None:
        """Fires before this minion's attack resolves."""

    def on_after_attack(self, target: Minion, ctx: CombatContext) -> None:
        """Fires after this minion's attack resolves (before death processing)."""

    def on_take_damage(self, amount: int, source: Minion | None, ctx: CombatContext) -> None:
        """Fires when this minion takes actual damage (not absorbed by shield)."""

    def on_kill(self, victim: Minion, ctx: CombatContext) -> None:
        """Fires when this minion kills another minion."""

    def on_friendly_death(self, dead: Minion, ctx: CombatContext) -> None:
        """Fires when a friendly minion dies (excluding self)."""

    def on_enemy_death(self, dead: Minion, ctx: CombatContext) -> None:
        """Fires when an enemy minion dies."""

    def on_friendly_summon(self, summoned: Minion, ctx: CombatContext) -> None:
        """Fires when a friendly minion is summoned during combat."""

    def on_divine_shield_lost(self, minion: Minion, ctx: CombatContext) -> None:
        """Fires when any friendly minion loses divine shield."""

    def on_overkill(self, victim: Minion, overkill_amount: int, ctx: CombatContext) -> None:
        """Fires when this minion deals excess lethal damage."""

    def on_avenge(self, ctx: CombatContext) -> None:
        """Fires when this minion's avenge counter reaches threshold."""

    def deathrattle(self, ctx: CombatContext, position: int) -> None:
        """Deathrattle effect. Position is where summoned tokens should go."""

    def has_deathrattle(self) -> bool:
        """Override to return True if this minion has a deathrattle."""
        return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clone(self) -> Minion:
        """Deep copy for simulation."""
        return deepcopy(self)

    def __repr__(self) -> str:
        kw_map = {
            "T": self.taunt,
            "DS": self.divine_shield,
            "P": self.poisonous,
            "V": self.venomous,
            "WF": self.windfury,
            "MWF": self.mega_windfury,
            "R": self.reborn,
            "C": self.cleave,
            "S": self.stealth,
        }
        keywords = [k for k, v in kw_map.items() if v]
        kw_str = f" [{','.join(keywords)}]" if keywords else ""
        return f"{self.name}({self.attack}/{self.health}{kw_str})"
