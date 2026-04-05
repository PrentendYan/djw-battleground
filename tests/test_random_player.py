# -*- coding: utf-8 -*-
"""Tests for RandomPlayer."""

from __future__ import annotations

import random

import pytest

from battleground.game.actions import (
    BuyMinionAction,
    EndTurnAction,
    RefreshTavernAction,
    SellMinionAction,
    UpgradeTavernAction,
)
from battleground.game.random_player import RandomPlayer
from battleground.game.state import GameState, MinionState, PlayerState


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def game() -> GameState:
    return GameState(
        players=(PlayerState(player_id=0, health=40),),
        current_turn=1,
    )


class TestRandomPlayer:
    def test_satisfies_protocol(self) -> None:
        p = RandomPlayer(player_id=0)
        assert p.player_id == 0

    def test_end_turn_when_no_options(self, rng: random.Random, game: GameState) -> None:
        p = RandomPlayer(player_id=0, rng=rng)
        ps = PlayerState(player_id=0, gold=0, board=())
        action = p.choose_action(ps, game, shop_size=0)
        assert isinstance(action, EndTurnAction)

    def test_can_buy_when_gold_and_shop(self, game: GameState) -> None:
        """With enough iterations, RandomPlayer should produce a buy action."""
        ps = PlayerState(player_id=0, gold=5)
        found_buy = False
        for seed in range(100):
            p = RandomPlayer(player_id=0, rng=random.Random(seed))
            action = p.choose_action(ps, game, shop_size=3)
            if isinstance(action, BuyMinionAction):
                found_buy = True
                assert 0 <= action.tavern_index < 3
                break
        assert found_buy, "RandomPlayer never produced BuyMinionAction in 100 tries"

    def test_can_upgrade(self, game: GameState) -> None:
        ps = PlayerState(player_id=0, gold=10, tavern_tier=1)
        found = False
        for seed in range(100):
            p = RandomPlayer(player_id=0, rng=random.Random(seed))
            action = p.choose_action(ps, game, shop_size=3, upgrade_discount=5)
            if isinstance(action, UpgradeTavernAction):
                found = True
                break
        assert found

    def test_can_sell(self, game: GameState) -> None:
        m = MinionState(card_id="T1_A", attack=1, health=1)
        ps = PlayerState(player_id=0, gold=0, board=(m,))
        found = False
        for seed in range(100):
            p = RandomPlayer(player_id=0, rng=random.Random(seed))
            action = p.choose_action(ps, game, shop_size=0)
            if isinstance(action, SellMinionAction):
                found = True
                break
        assert found

    def test_deterministic_with_seed(self, game: GameState) -> None:
        ps = PlayerState(player_id=0, gold=5)
        p1 = RandomPlayer(player_id=0, rng=random.Random(42))
        p2 = RandomPlayer(player_id=0, rng=random.Random(42))
        a1 = p1.choose_action(ps, game, shop_size=3)
        a2 = p2.choose_action(ps, game, shop_size=3)
        assert a1 == a2
