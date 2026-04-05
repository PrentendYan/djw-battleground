# -*- coding: utf-8 -*-
"""Tests for BattleAPI — state conversion and combat integration."""

from battleground.game.state import (
    GameState,
    MinionState,
    PlayerState,
)
from battleground.game.battle_api import BattleAPI


class TestMinionToEntity:
    """Test MinionState → Firestone BoardEntity dict conversion."""

    def test_basic_minion(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3)
        entity = BattleAPI._minion_to_entity(m)
        assert entity["cardId"] == "BGS_039"
        assert entity["attack"] == 3
        assert entity["health"] == 3
        assert entity["friendly"] is True
        assert "taunt" not in entity

    def test_minion_with_keywords(self):
        m = MinionState(
            card_id="BGS_061",
            attack=2,
            health=1,
            taunt=True,
            divine_shield=True,
            reborn=True,
        )
        entity = BattleAPI._minion_to_entity(m)
        assert entity["taunt"] is True
        assert entity["divineShield"] is True
        assert entity["reborn"] is True
        assert "poisonous" not in entity

    def test_opponent_minion(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3)
        entity = BattleAPI._minion_to_entity(m, friendly=False)
        assert entity["friendly"] is False

    def test_minion_with_enchantments(self):
        m = MinionState(
            card_id="BGS_039",
            attack=3,
            health=3,
            enchantments=({"cardId": "ENC_001"},),
        )
        entity = BattleAPI._minion_to_entity(m)
        assert entity["enchantments"] == [{"cardId": "ENC_001"}]

    def test_tavern_tier_omitted_when_1(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3, tavern_tier=1)
        entity = BattleAPI._minion_to_entity(m)
        assert "tavernTier" not in entity

    def test_tavern_tier_included_when_not_1(self):
        m = MinionState(card_id="BGS_039", attack=3, health=3, tavern_tier=3)
        entity = BattleAPI._minion_to_entity(m)
        assert entity["tavernTier"] == 3


class TestBuildBattleInfo:
    """Test PlayerState → BgsBattleInfo dict conversion."""

    def _make_player(self, **kwargs):
        board = (MinionState(card_id="BGS_039", attack=3, health=3),)
        defaults = {"player_id": 0, "board": board, "tavern_tier": 2}
        defaults.update(kwargs)
        return PlayerState(**defaults)

    def test_basic_battle_info(self):
        p = self._make_player(player_id=0)
        o = self._make_player(player_id=1)
        info = BattleAPI._build_battle_info(p, o)

        assert info["playerBoard"]["player"]["tavernTier"] == 2
        assert len(info["playerBoard"]["board"]) == 1
        assert info["opponentBoard"]["board"][0]["friendly"] is False
        assert info["options"]["numberOfSimulations"] == 10000
        assert info["gameState"]["anomalies"] == []

    def test_hero_powers_passed(self):
        p = self._make_player(
            hero_powers=({"cardId": "HP_001", "isUsed": False},),
        )
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        assert info["playerBoard"]["player"]["heroPowers"] == [
            {"cardId": "HP_001", "isUsed": False}
        ]

    def test_secrets_passed(self):
        p = self._make_player(
            secrets=({"cardId": "SEC_001"},),
        )
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        assert info["playerBoard"]["secrets"] == [{"cardId": "SEC_001"}]

    def test_trinkets_passed(self):
        p = self._make_player(
            trinkets=({"cardId": "TRK_001"},),
        )
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        assert info["playerBoard"]["player"]["trinkets"] == [{"cardId": "TRK_001"}]

    def test_anomalies_passed(self):
        p = self._make_player()
        o = self._make_player()
        info = BattleAPI._build_battle_info(
            p, o, anomalies=("ANOMALY_001",)
        )
        assert info["gameState"]["anomalies"] == ["ANOMALY_001"]

    def test_global_info_passed(self):
        p = self._make_player(
            global_info={"EternalKnightDeadCount": 5},
        )
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        assert info["playerBoard"]["player"]["globalInfo"] == {"EternalKnightDeadCount": 5}

    def test_global_info_omitted_when_none(self):
        p = self._make_player()
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        assert "globalInfo" not in info["playerBoard"]["player"]

    def test_hand_passed(self):
        hand = (MinionState(card_id="BGS_100", attack=5, health=5, tavern_tier=3),)
        p = self._make_player(hand=hand)
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        player_hand = info["playerBoard"]["player"]["hand"]
        assert len(player_hand) == 1
        assert player_hand[0]["cardId"] == "BGS_100"
        assert player_hand[0]["attack"] == 5
        assert player_hand[0]["health"] == 5
        assert player_hand[0]["friendly"] is True

    def test_hand_omitted_when_empty(self):
        p = self._make_player()
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        assert "hand" not in info["playerBoard"]["player"]

    def test_hand_multiple_minions(self):
        hand = (
            MinionState(card_id="BGS_100", attack=5, health=5),
            MinionState(card_id="BGS_101", attack=2, health=3, taunt=True),
        )
        p = self._make_player(hand=hand)
        o = self._make_player()
        info = BattleAPI._build_battle_info(p, o)
        player_hand = info["playerBoard"]["player"]["hand"]
        assert len(player_hand) == 2
        assert player_hand[1]["cardId"] == "BGS_101"
        assert player_hand[1]["taunt"] is True


class TestMatchmaking:
    """Test matchmaking pairing logic."""

    def test_even_players_all_paired(self):
        from battleground.game.matchmaking import Matchmaker
        import random

        players = tuple(PlayerState(player_id=i) for i in range(8))
        game = GameState(players=players)
        mm = Matchmaker()
        pairs = mm.pair(game, rng=random.Random(42))
        assert len(pairs) == 4
        all_ids = set()
        for p1, p2 in pairs:
            all_ids.add(p1.player_id)
            all_ids.add(p2.player_id)
        assert all_ids == set(range(8))

    def test_odd_players_ghost(self):
        from battleground.game.matchmaking import Matchmaker
        import random

        players = list(PlayerState(player_id=i) for i in range(7))
        players.append(PlayerState(player_id=7, health=0, finished_position=8))
        game = GameState(players=tuple(players))
        mm = Matchmaker()
        pairs = mm.pair(game, rng=random.Random(42))
        # 7 alive → 3 normal pairs + 1 ghost pair = 4
        assert len(pairs) == 4
        # Every alive player must appear in exactly one pair
        paired_ids = set()
        for p1, p2 in pairs:
            paired_ids.add(p1.player_id)
            if p2.player_id != -1:
                paired_ids.add(p2.player_id)
        alive_ids = {p.player_id for p in game.alive_players}
        assert paired_ids == alive_ids
        # Exactly one ghost pair
        ghost_pairs = [(p1, p2) for p1, p2 in pairs if p2.player_id == -1]
        assert len(ghost_pairs) == 1

    def test_history_update(self):
        from battleground.game.matchmaking import Matchmaker

        p0 = PlayerState(player_id=0)
        p1 = PlayerState(player_id=1)
        game = GameState(players=(p0, p1))
        mm = Matchmaker()
        pairs = [(p0, p1)]
        updated = mm.update_history(game, pairs)
        # pairing_history is now tuple[tuple[int, tuple[int, ...]], ...]
        history_dict = dict(updated.pairing_history)
        assert 1 in history_dict[0]
        assert 0 in history_dict[1]

    def test_all_players_paired_even_with_saturated_history(self):
        """4 players where history blocks all natural pairings."""
        from battleground.game.matchmaking import Matchmaker
        import random

        players = tuple(PlayerState(player_id=i) for i in range(4))
        # Everyone has faced everyone recently
        history = tuple(
            (i, tuple(j for j in range(4) if j != i))
            for i in range(4)
        )
        game = GameState(players=players, pairing_history=history)
        mm = Matchmaker()
        pairs = mm.pair(game, rng=random.Random(42))
        assert len(pairs) == 2
        paired_ids = set()
        for p1, p2 in pairs:
            paired_ids.add(p1.player_id)
            paired_ids.add(p2.player_id)
        assert paired_ids == {0, 1, 2, 3}
