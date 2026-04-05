# -*- coding: utf-8 -*-
"""Monte Carlo combat simulator."""

from __future__ import annotations

import random as _random

from .board import Board
from .combat import CombatEngine
from .types import CombatResult, SimulationResult


class Simulator:
    """Run N combat simulations and aggregate results."""

    def __init__(
        self,
        board0: Board,
        board1: Board,
        hero_tiers: tuple[int, int] = (1, 1),
        num_simulations: int = 10_000,
        seed: int | None = None,
    ) -> None:
        self._board0 = board0
        self._board1 = board1
        self._hero_tiers = hero_tiers
        self._num_simulations = num_simulations
        self._rng = _random.Random(seed)

    def run(self) -> SimulationResult:
        result = SimulationResult(total=self._num_simulations)

        for _ in range(self._num_simulations):
            b0 = self._board0.clone()
            b1 = self._board1.clone()
            # Each sim gets its own RNG derived from the main one
            sim_rng = _random.Random(self._rng.randint(0, 2**63))
            engine = CombatEngine(b0, b1, self._hero_tiers, rng=sim_rng)
            outcome = engine.run()

            if outcome.result == CombatResult.WIN:
                result.wins += 1
                result.win_damages.append(outcome.damage)
            elif outcome.result == CombatResult.LOSS:
                result.losses += 1
                result.loss_damages.append(outcome.damage)
            else:
                result.ties += 1

        return result
