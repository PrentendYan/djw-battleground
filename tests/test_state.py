# -*- coding: utf-8 -*-
"""Tests for game state types."""

import pytest
from dataclasses import replace

from battleground.game.state import (
    GamePhase,
    GameState,
    HeroState,
    MinionState,
    PlayerState,
)


class TestMinionState:
    def test_default_minion(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3)
        assert m.card_id == "BGS_039"
        assert m.attack == 3
        assert m.health == 3
        assert m.tavern_tier == 1
        assert not m.taunt
        assert not m.divine_shield

    def test_minion_with_keywords(self):
        m = MinionState(
            card_id="BGS_061",
            attack=2,
            health=1,
            taunt=True,
            divine_shield=True,
            reborn=True,
        )
        assert m.taunt
        assert m.divine_shield
        assert m.reborn

    def test_minion_is_frozen(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3)
        with pytest.raises(AttributeError):
            m.attack = 5  # type: ignore[misc]

    def test_minion_replace(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3)
        m2 = replace(m, attack=5)
        assert m.attack == 3
        assert m2.attack == 5


class TestHeroState:
    def test_default_hero(self):
        h = HeroState()
        assert h.card_id == "TB_BaconShop_HERO_01"
        assert h.hero_power_card_id == ""
        assert not h.hero_power_used


class TestPlayerState:
    def test_default_player(self):
        p = PlayerState(player_id=0)
        assert p.health == 40
        assert p.armor == 0
        assert p.tavern_tier == 1
        assert p.alive
        assert not p.is_dead
        assert p.effective_health == 40
        assert p.board == ()
        assert p.hand == ()

    def test_player_with_board(self):
        board = (
            MinionState(card_id="BGS_039", attack=3, health=3),
            MinionState(card_id="BGS_061", attack=2, health=1, taunt=True),
        )
        p = PlayerState(player_id=1, board=board)
        assert len(p.board) == 2
        assert p.board[0].card_id == "BGS_039"

    def test_effective_health_with_armor(self):
        p = PlayerState(player_id=0, health=30, armor=10)
        assert p.effective_health == 40

    def test_is_dead(self):
        p = PlayerState(player_id=0, health=0)
        assert p.is_dead

    def test_player_s6_fields_default_empty(self):
        p = PlayerState(player_id=0)
        assert p.hero_powers == ()
        assert p.secrets == ()
        assert p.trinkets == ()
        assert p.quest_entities == ()
        assert p.global_info is None


class TestGameState:
    @pytest.fixture()
    def eight_players(self):
        return tuple(PlayerState(player_id=i) for i in range(8))

    def test_initial_game(self, eight_players):
        g = GameState(players=eight_players)
        assert g.current_turn == 1
        assert g.phase == GamePhase.RECRUIT
        assert g.num_alive == 8
        assert not g.is_game_over

    def test_alive_players(self, eight_players):
        players = list(eight_players)
        players[3] = replace(players[3], health=0)
        g = GameState(players=tuple(players))
        assert g.num_alive == 7
        assert all(p.player_id != 3 for p in g.alive_players)

    def test_game_over(self):
        players = (
            PlayerState(player_id=0),
            PlayerState(player_id=1, health=0),
        )
        g = GameState(players=players)
        assert g.is_game_over

    def test_alive_is_derived_from_health(self):
        p = PlayerState(player_id=0, health=10)
        assert p.alive
        p_dead = replace(p, health=0)
        assert not p_dead.alive
        assert p_dead.is_dead

    def test_get_player(self, eight_players):
        g = GameState(players=eight_players)
        p = g.get_player(5)
        assert p is not None
        assert p.player_id == 5
        assert g.get_player(99) is None
