# -*- coding: utf-8 -*-
"""Combat engine — full combat resolution with two-step death processing."""

from __future__ import annotations

import random as _random

from .board import Board
from .minion import Minion
from .types import CombatOutcome, CombatResult


class CombatContext:
    """Provides controlled access to combat state for minion hooks.

    Each side has its own context instance so that ``own_board`` /
    ``enemy_board`` are always correct from the caller's perspective.
    """

    def __init__(self, engine: CombatEngine, board_idx: int) -> None:
        self._engine = engine
        self._board_idx = board_idx

    @property
    def own_board(self) -> Board:
        return self._engine.boards[self._board_idx]

    @property
    def enemy_board(self) -> Board:
        return self._engine.boards[1 - self._board_idx]

    def summon(self, minion: Minion, position: int | None = None) -> bool:
        """Summon a minion on own board at *position* (or rightmost)."""
        board = self.own_board
        actual_pos = position
        if actual_pos is not None:
            actual_pos = min(max(0, actual_pos), len(board))
        success = board.add(minion, actual_pos)
        if success:
            self._engine._on_summon(minion, self._board_idx)
        return success

    def deal_damage_to(self, target: Minion, amount: int, source: Minion | None = None) -> int:
        """Deal *amount* damage to *target*. Returns actual damage dealt."""
        return self._engine._deal_damage(target, amount, source)

    def buff(self, target: Minion, attack: int = 0, health: int = 0) -> None:
        target.attack += attack
        if health > 0:
            target.health += health


class CombatEngine:
    """Resolves a single Battlegrounds combat between two boards.

    Key design:
    - Two-step death processing (collect → trigger deathrattles)
    - Deathrattles fire in entry-order, attacker's side first
    - Reborn fires after all deathrattles in the same death batch
    - Chain deaths are re-checked until no new deaths occur
    """

    MAX_TURNS = 200  # Safety valve against infinite loops

    def __init__(
        self,
        board0: Board,
        board1: Board,
        hero_tiers: tuple[int, int] = (1, 1),
        rng: _random.Random | None = None,
    ) -> None:
        self.boards: list[Board] = [board0, board1]
        self.hero_tiers = hero_tiers
        self.rng: _random.Random = rng or _random.Random()
        self._current_attacker: int = 0
        self._entry_counter: int = 0
        self._contexts: list[CombatContext] = [
            CombatContext(self, 0),
            CombatContext(self, 1),
        ]

    # ==================================================================
    # Public API
    # ==================================================================

    def run(self) -> CombatOutcome:
        """Execute the full combat and return the outcome."""
        self._assign_entry_orders()
        self._determine_first_attacker()
        self._start_of_combat()

        turns = 0
        while not self.boards[0].is_empty and not self.boards[1].is_empty:
            if turns >= self.MAX_TURNS:
                break  # stalemate guard

            attacker_board = self.boards[self._current_attacker]
            defender_board = self.boards[1 - self._current_attacker]

            attacker = attacker_board.get_next_attacker()
            if attacker is not None:
                for _ in range(attacker.num_attacks):
                    if not attacker.is_alive or defender_board.is_empty:
                        break
                    target = defender_board.get_random_target(rng=self.rng)
                    if target is None:
                        break
                    self._resolve_attack(attacker, target)
                    self._process_deaths()
                    if not attacker.is_alive or defender_board.is_empty:
                        break

            self._current_attacker = 1 - self._current_attacker
            turns += 1

        return self._calculate_outcome()

    # ==================================================================
    # Setup
    # ==================================================================

    def _assign_entry_orders(self) -> None:
        """Give each starting minion a unique entry order."""
        counter = 0
        for side in range(2):
            for minion in self.boards[side].minions:
                minion._entry_order = counter
                counter += 1
        self._entry_counter = counter

    def _next_entry_order(self) -> int:
        eo = self._entry_counter
        self._entry_counter += 1
        return eo

    def _determine_first_attacker(self) -> None:
        n0 = len(self.boards[0])
        n1 = len(self.boards[1])
        if n0 > n1:
            self._current_attacker = 0
        elif n1 > n0:
            self._current_attacker = 1
        else:
            self._current_attacker = self.rng.randint(0, 1)

    def _start_of_combat(self) -> None:
        """Trigger Start of Combat effects (attacker side first)."""
        for side in [self._current_attacker, 1 - self._current_attacker]:
            for minion in list(self.boards[side].minions):
                minion.on_start_of_combat(self._contexts[side])
        self._process_deaths()

    # ==================================================================
    # Attack resolution
    # ==================================================================

    def _resolve_attack(self, attacker: Minion, target: Minion) -> None:
        attacker_side = self._find_side(attacker) or 0
        defender_side = 1 - attacker_side

        # Stealth breaks on attack
        if attacker.stealth:
            attacker.stealth = False

        # Pre-attack hooks
        attacker.on_pre_attack(target, self._contexts[attacker_side])

        # --- Attacker hits target ---
        atk_dmg = attacker.attack
        self._deal_damage(target, atk_dmg, attacker)

        # Cleave: damage adjacent minions
        if attacker.cleave and target in self.boards[defender_side].minions:
            left, right = self.boards[defender_side].get_adjacent(target)
            if left is not None:
                self._deal_damage(left, atk_dmg, attacker)
            if right is not None:
                self._deal_damage(right, atk_dmg, attacker)

        # --- Target hits attacker (counter-attack) ---
        if target.attack > 0:
            self._deal_damage(attacker, target.attack, target)

        # Post-attack hooks
        attacker.on_after_attack(target, self._contexts[attacker_side])

    def _deal_damage(self, target: Minion, amount: int, source: Minion | None = None) -> int:
        """Deal damage to a minion. Returns actual damage dealt (0 if shielded)."""
        if amount <= 0:
            return 0

        # Divine Shield absorbs all damage
        if target.divine_shield:
            target.divine_shield = False
            self._notify_divine_shield_lost(target)
            return 0

        # Apply damage
        target.health -= amount
        actual = amount

        # Poisonous / Venomous: ensure kill
        if source is not None and target.health > 0:
            if source.poisonous:
                target.health = 0
            elif source.venomous:
                target.health = 0
                source.venomous = False

        # Hook: on_take_damage
        target_side = self._find_side(target)
        if target_side is not None:
            target.on_take_damage(actual, source, self._contexts[target_side])

        return actual

    # ==================================================================
    # Death processing (two-step algorithm)
    # ==================================================================

    def _process_deaths(self) -> None:
        """Collect dead → remove → deathrattles → reborn → repeat until stable."""
        while True:
            # Step 1: Collect all dead minions with their current positions
            dead_by_side: list[list[tuple[Minion, int]]] = [[], []]
            for side in range(2):
                for minion in list(self.boards[side].minions):
                    if not minion.is_alive:
                        pos = self.boards[side].get_position(minion)
                        dead_by_side[side].append((minion, pos))

            if not dead_by_side[0] and not dead_by_side[1]:
                break

            # Step 2: Remove dead minions (reverse order to preserve indices)
            for side in range(2):
                for minion, _ in sorted(dead_by_side[side], key=lambda x: x[1], reverse=True):
                    self.boards[side].remove(minion)

            # Step 3: Calculate adjusted summon positions
            summon_pos: dict[int, int] = {}
            for side in range(2):
                dead_positions = sorted(pos for _, pos in dead_by_side[side])
                for minion, orig_pos in dead_by_side[side]:
                    offset = sum(1 for dp in dead_positions if dp < orig_pos)
                    summon_pos[id(minion)] = orig_pos - offset

            # Step 4: Notify death hooks (avenge counters, etc.)
            for side in range(2):
                for dead_minion, _ in dead_by_side[side]:
                    # Notify friendly surviving minions
                    for alive in list(self.boards[side].minions):
                        alive.on_friendly_death(dead_minion, self._contexts[side])
                        # Avenge counter
                        if alive._avenge_threshold > 0:
                            alive._avenge_counter += 1
                            if alive._avenge_counter >= alive._avenge_threshold:
                                alive._avenge_counter = 0
                                alive.on_avenge(self._contexts[side])
                    # Notify enemy surviving minions
                    for alive in list(self.boards[1 - side].minions):
                        alive.on_enemy_death(dead_minion, self._contexts[1 - side])

            # Notify killers
            for side in range(2):
                for dead_minion, _ in dead_by_side[side]:
                    enemy_side = 1 - side
                    for alive in list(self.boards[enemy_side].minions):
                        # Simplified: can't precisely track who killed whom
                        # in multi-target scenarios (cleave). Full tracking
                        # is added per-minion in S2.
                        pass

            # Step 5: Trigger deathrattles (attacker side first, entry order)
            for side in [self._current_attacker, 1 - self._current_attacker]:
                dead_sorted = sorted(dead_by_side[side], key=lambda x: x[0]._entry_order)
                multiplier = self._get_deathrattle_multiplier(side)
                for minion, _ in dead_sorted:
                    if minion.has_deathrattle():
                        pos = summon_pos.get(id(minion), 0)
                        for _ in range(multiplier):
                            minion.deathrattle(self._contexts[side], pos)

            # Step 6: Handle reborn
            for side in range(2):
                dead_sorted = sorted(dead_by_side[side], key=lambda x: x[0]._entry_order)
                for minion, _ in dead_sorted:
                    if minion.reborn and not minion._reborn_triggered:
                        reborn_copy = minion.clone()
                        reborn_copy.health = 1
                        reborn_copy.reborn = False
                        reborn_copy._reborn_triggered = True
                        reborn_copy._entry_order = self._next_entry_order()
                        pos = summon_pos.get(id(minion), len(self.boards[side]))
                        actual_pos = min(pos, len(self.boards[side]))
                        self.boards[side].add(reborn_copy, actual_pos)

            # Loop: check for chain deaths (deathrattle damage, aura loss, etc.)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _get_deathrattle_multiplier(self, side: int) -> int:
        """Check board for Baron Rivendare type effects."""
        multiplier = 1
        for m in self.boards[side].minions:
            multiplier = max(multiplier, m.deathrattle_multiplier)
        return multiplier

    def _find_side(self, minion: Minion) -> int | None:
        """Find which side a minion belongs to. Returns None if not on board."""
        for side in range(2):
            if minion in self.boards[side].minions:
                return side
        return None

    def _notify_divine_shield_lost(self, minion: Minion) -> None:
        side = self._find_side(minion)
        if side is not None:
            for m in list(self.boards[side].minions):
                m.on_divine_shield_lost(minion, self._contexts[side])

    def _on_summon(self, minion: Minion, side: int) -> None:
        """Called when a new minion is summoned during combat."""
        minion._entry_order = self._next_entry_order()
        for m in list(self.boards[side].minions):
            if m is not minion:
                m.on_friendly_summon(minion, self._contexts[side])

    def _calculate_outcome(self) -> CombatOutcome:
        b0_empty = self.boards[0].is_empty
        b1_empty = self.boards[1].is_empty

        if b0_empty and b1_empty:
            return CombatOutcome(result=CombatResult.DRAW, damage=0, winning_side=-1)

        if b1_empty:
            damage = self.hero_tiers[0] + sum(m.tier for m in self.boards[0].minions)
            return CombatOutcome(result=CombatResult.WIN, damage=damage, winning_side=0)

        # b0_empty
        damage = self.hero_tiers[1] + sum(m.tier for m in self.boards[1].minions)
        return CombatOutcome(result=CombatResult.LOSS, damage=damage, winning_side=1)
