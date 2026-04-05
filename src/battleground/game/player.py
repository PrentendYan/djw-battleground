# -*- coding: utf-8 -*-
"""Player protocol — interface for human and AI players (future).

This module defines the Player protocol that any agent or human controller
must implement.  Concrete implementations (RandomPlayer, RLPlayer, etc.)
will be added in S7.
"""

from __future__ import annotations

from typing import Protocol

from .actions import Action
from .state import GameState, PlayerState


class Player(Protocol):
    """Interface that all player implementations must satisfy."""

    @property
    def player_id(self) -> int: ...

    def choose_action(self, own_state: PlayerState, game: GameState) -> Action:
        """Choose the next recruit-phase action given current state.

        Called repeatedly during the recruit phase until the player
        returns ``EndTurnAction`` or the timer expires.
        """
        ...
