# -*- coding: utf-8 -*-
"""Battlegrounds matchmaking — pair alive players for combat each round."""

from __future__ import annotations

import logging
import random
from dataclasses import replace

from .state import GameState, PlayerState

logger = logging.getLogger(__name__)


class Matchmaker:
    """Standard BG matchmaking with 3-round anti-repeat and ghost player.

    Usage::

        matchmaker = Matchmaker()
        pairs = matchmaker.pair(game_state)
        # pairs: list of (PlayerState, PlayerState) — second may be ghost
    """

    HISTORY_WINDOW = 3  # Avoid re-matching within this many rounds

    def pair(
        self,
        game: GameState,
        rng: random.Random | None = None,
    ) -> list[tuple[PlayerState, PlayerState]]:
        """Return combat pairings for this round.

        If odd number alive, one player fights the ghost (copy of
        most recently eliminated player's board).
        Every alive player is guaranteed to appear in exactly one pair.
        """
        rng = rng or random.Random()
        alive = list(game.alive_players)
        rng.shuffle(alive)

        ghost: PlayerState | None = None
        if len(alive) % 2 == 1:
            ghost = self._make_ghost(game)

        pairs: list[tuple[PlayerState, PlayerState]] = []
        used: set[int] = set()

        for player in alive:
            if player.player_id in used:
                continue
            candidates = [
                p for p in alive
                if p.player_id != player.player_id
                and p.player_id not in used
                and not self._recently_faced(game, player.player_id, p.player_id)
            ]
            if not candidates:
                # Fallback: allow re-matching if no valid candidates
                candidates = [
                    p for p in alive
                    if p.player_id != player.player_id
                    and p.player_id not in used
                ]

            if candidates:
                opponent = rng.choice(candidates)
                pairs.append((player, opponent))
                used.add(player.player_id)
                used.add(opponent.player_id)

        # Remaining unpaired players fight ghost (should be at most 1)
        unpaired = [p for p in alive if p.player_id not in used]
        if len(unpaired) > 1:
            # Edge case: history saturation left multiple players unpaired.
            # Force-pair them with each other, ignoring history.
            logger.warning(f"History saturation: {len(unpaired)} unpaired players, force-pairing")
            while len(unpaired) >= 2:
                p1 = unpaired.pop()
                p2 = unpaired.pop()
                pairs.append((p1, p2))

        if unpaired and ghost is not None:
            pairs.append((unpaired[0], ghost))
        elif unpaired and ghost is None:
            # Even count but someone still unpaired — force ghost
            logger.warning("Even-count lobby with unpaired player, creating emergency ghost")
            ghost = self._make_ghost(game)
            pairs.append((unpaired[0], ghost))

        return pairs

    def update_history(
        self,
        game: GameState,
        pairs: list[tuple[PlayerState, PlayerState]],
    ) -> GameState:
        """Record this round's pairings into game state history."""
        # Convert immutable history to mutable dict for update
        history: dict[int, list[int]] = {}
        for pid, opps in game.pairing_history:
            history[pid] = list(opps)

        for p1, p2 in pairs:
            history.setdefault(p1.player_id, []).append(p2.player_id)
            history.setdefault(p2.player_id, []).append(p1.player_id)
            # Trim to window
            history[p1.player_id] = history[p1.player_id][-self.HISTORY_WINDOW:]
            history[p2.player_id] = history[p2.player_id][-self.HISTORY_WINDOW:]

        # Convert back to immutable format
        new_history = tuple(
            (pid, tuple(opps)) for pid, opps in history.items()
        )
        return replace(game, pairing_history=new_history)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _recently_faced(game: GameState, pid: int, oid: int) -> bool:
        return oid in game.get_recent_opponents(pid)

    @staticmethod
    def _make_ghost(game: GameState) -> PlayerState:
        """Create a ghost player from the most recently eliminated player."""
        dead = [p for p in game.players if p.is_dead]
        if not dead:
            # No one dead yet — return an empty ghost with 1 HP
            # (Firestone needs positive hpLeft)
            return PlayerState(player_id=-1, health=1)
        # Most recently eliminated = highest finished_position among dead
        most_recent = max(dead, key=lambda p: p.finished_position)
        # Ghost gets the eliminated player's board but with 1 HP
        # (ghost health doesn't matter for BG rules, but Firestone needs >0)
        return replace(most_recent, player_id=-1, health=1)
