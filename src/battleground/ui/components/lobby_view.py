# -*- coding: utf-8 -*-
"""Lobby view component — display 8-player game state overview (placeholder for S7)."""

from __future__ import annotations

import streamlit as st

from battleground.game.state import GameState


def render_lobby(game: GameState) -> None:
    """Render an overview of all 8 players in a lobby."""
    st.subheader(f"Lobby — Turn {game.current_turn} ({game.phase.name})")
    st.caption(f"{game.num_alive} players alive")

    cols = st.columns(4)
    for i, player in enumerate(game.players):
        with cols[i % 4]:
            status = "ALIVE" if player.alive else f"#{player.finished_position}"
            color = "green" if player.alive else "red"
            st.markdown(
                f"**P{player.player_id}** :{color}[{status}]  \n"
                f"HP: {player.health} + {player.armor} armor  \n"
                f"Tier: {player.tavern_tier}  \n"
                f"Board: {len(player.board)} minions"
            )
