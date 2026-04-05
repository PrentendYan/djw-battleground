# -*- coding: utf-8 -*-
"""RandomPlayer — makes random recruit-phase decisions."""

from __future__ import annotations

import random

from .actions import (
    Action,
    BuyMinionAction,
    EndTurnAction,
    RefreshTavernAction,
    SellMinionAction,
    UpgradeTavernAction,
)
from .recruit import BUY_COST, REFRESH_COST, upgrade_cost
from .state import GameState, PlayerState


class RandomPlayer:
    """Random AI that buys/sells/upgrades with weighted probabilities.

    Satisfies the ``Player`` protocol defined in ``player.py``.
    """

    def __init__(self, player_id: int, rng: random.Random | None = None) -> None:
        self._player_id = player_id
        self._rng = rng or random.Random()

    @property
    def player_id(self) -> int:
        return self._player_id

    def choose_action(
        self,
        own_state: PlayerState,
        game: GameState,
        *,
        shop_size: int = 0,
        upgrade_discount: int = 0,
    ) -> Action:
        """Pick a random legal action.

        Extra kwargs ``shop_size`` and ``upgrade_discount`` are passed by the
        game loop to give the player enough context without exposing ShopState
        internals.
        """
        options: list[Action] = []

        # Buy (if gold ≥ 3 and shop non-empty and board+hand not full)
        if own_state.gold >= BUY_COST and shop_size > 0:
            if len(own_state.board) + len(own_state.hand) < 17:
                idx = self._rng.randrange(shop_size)
                options.append(BuyMinionAction(tavern_index=idx))

        # Sell (if board non-empty)
        if own_state.board:
            idx = self._rng.randrange(len(own_state.board))
            options.append(SellMinionAction(board_index=idx))

        # Upgrade (if affordable)
        if own_state.tavern_tier < 6:
            cost = upgrade_cost(own_state.tavern_tier, upgrade_discount)
            if own_state.gold >= cost:
                options.append(UpgradeTavernAction())

        # Refresh (if gold ≥ 1)
        if own_state.gold >= REFRESH_COST:
            options.append(RefreshTavernAction())

        if not options:
            return EndTurnAction()

        # Weight: buy > upgrade > refresh > sell > end
        weights = []
        for opt in options:
            match opt:
                case BuyMinionAction():
                    weights.append(5)
                case UpgradeTavernAction():
                    weights.append(3)
                case RefreshTavernAction():
                    weights.append(2)
                case SellMinionAction():
                    weights.append(1)
                case _:
                    weights.append(1)

        # Always include EndTurn as an option (low weight)
        options.append(EndTurnAction())
        weights.append(1)

        return self._rng.choices(options, weights=weights, k=1)[0]
