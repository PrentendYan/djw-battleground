# -*- coding: utf-8 -*-
"""Game simulation viewer — run and observe full BG games in Streamlit."""

from __future__ import annotations

import json
import random
from pathlib import Path

import streamlit as st

from battleground.game.game_loop import GameLoop, TurnLog
from battleground.game.minion_pool import MinionPool
from battleground.game.random_player import RandomPlayer
from battleground.game.state import GameState, PlayerState

_CARDS_PATH = Path(__file__).parents[4] / "data" / "cards_cache.json"


@st.cache_data
def _load_cards() -> list[dict]:
    with open(_CARDS_PATH) as f:
        return json.load(f)


def _start_game(num_players: int, seed: int) -> None:
    """Create a new GameLoop and store in session_state."""
    cards = _load_cards()
    pool = MinionPool.from_cards(cards)
    rng = random.Random(seed)
    players = [RandomPlayer(i, random.Random(seed + i)) for i in range(num_players)]
    loop = GameLoop(players, pool, rng=rng)
    st.session_state["sim_loop"] = loop
    st.session_state["sim_history"] = [loop.game]


def _step_game() -> None:
    loop: GameLoop = st.session_state["sim_loop"]
    loop.step()
    st.session_state["sim_history"].append(loop.game)


def _run_n_turns(n: int) -> None:
    loop: GameLoop = st.session_state["sim_loop"]
    for _ in range(n):
        if loop.game.is_game_over:
            break
        loop.step()
        st.session_state["sim_history"].append(loop.game)


# ── Public entry points ──────────────────────────────────────────────

def render_simulation_sidebar() -> None:
    """Sidebar controls for game simulation mode."""
    st.header("Game Simulation")

    num_players = st.selectbox("Players", [2, 4, 6, 8], index=3, key="sim_num_players")
    seed = st.number_input("Seed", 0, 99999, 42, key="sim_seed")

    if st.button("Start New Game", use_container_width=True, key="sim_start"):
        _start_game(num_players, seed)

    if "sim_loop" not in st.session_state:
        return

    loop: GameLoop = st.session_state["sim_loop"]
    game = loop.game

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Turn", game.current_turn)
    c2.metric("Alive", f"{game.num_alive}/{len(game.players)}")

    if game.is_game_over:
        st.success("Game over!")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("+ 1", key="sim_step1", on_click=_step_game)
    with col2:
        st.button("+ 5", key="sim_step5", on_click=lambda: _run_n_turns(5))
    with col3:
        st.button("End", key="sim_end", on_click=lambda: _run_n_turns(40))


def render_simulation_main() -> None:
    """Main area for game simulation mode."""
    if "sim_loop" not in st.session_state:
        st.info("Click **Start New Game** in the sidebar.")
        return

    loop: GameLoop = st.session_state["sim_loop"]
    history: list[GameState] = st.session_state.get("sim_history", [])

    # Turn slider to browse history
    view_turn = 0
    if len(history) > 1:
        view_turn = st.slider(
            "Browse turns",
            0, len(history) - 1,
            len(history) - 1,
            key="sim_turn_slider",
        )

    game = history[view_turn]
    _render_lobby(game)

    # Turn log for the viewed turn
    turn_num = game.current_turn
    if turn_num > 0 and turn_num in loop.turn_logs:
        _render_turn_log(loop.turn_logs[turn_num])

    # Per-player detail (expandable)
    for player in sorted(game.players, key=lambda p: (p.is_dead, -p.player_id)):
        _render_player_expander(player, loop.turn_logs.get(turn_num))


# ── Lobby grid ───────────────────────────────────────────────────────

def _render_lobby(game: GameState) -> None:
    st.subheader(f"Turn {game.current_turn} | {game.num_alive} alive")
    cols = st.columns(4)
    for i, player in enumerate(game.players):
        with cols[i % 4]:
            _render_player_card(player)


def _render_player_card(p: PlayerState) -> None:
    if p.alive:
        hp_text = f"{p.health}" + (f"+{p.armor}" if p.armor else "")
        header = f"**P{p.player_id}** :green[HP {hp_text}]"
    else:
        header = f"**P{p.player_id}** :red[#{p.finished_position}]"

    board_str = ""
    if p.board:
        parts = []
        for m in p.board:
            g = "G" if m.golden else ""
            parts.append(f"{g}{m.attack}/{m.health}")
        board_str = " ".join(parts)

    st.markdown(
        f"{header}  \n"
        f"Tier {p.tavern_tier} | Board {len(p.board)}/7"
        + (f" | Hand {len(p.hand)}" if p.hand else "")
        + (f"  \n`{board_str}`" if board_str else "")
    )


# ── Turn log ─────────────────────────────────────────────────────────

def _render_turn_log(tlog: TurnLog) -> None:
    """Show a summary table of what every player did this turn."""
    st.subheader(f"Turn {tlog.turn} — Recruit & Combat Log")

    rows = []
    for pl in tlog.player_logs:
        shop_str = ", ".join(pl.shop_offered) if pl.shop_offered else "-"
        actions_str = " > ".join(pl.actions) if pl.actions else "(no actions)"
        rows.append({
            "Player": f"P{pl.player_id}",
            "Gold": f"{pl.gold_given}g (-{pl.gold_spent})",
            "Shop": shop_str,
            "Actions": actions_str,
            "Board": f"{pl.board_after}/7",
            "Tier": pl.tier_after,
            "vs": f"P{pl.opponent_id}" if pl.opponent_id is not None else "-",
            "Combat": pl.combat_result or "-",
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)


# ── Player detail expander ───────────────────────────────────────────

def _render_player_expander(p: PlayerState, tlog: TurnLog | None) -> None:
    if p.alive:
        label = f"P{p.player_id} — HP {p.health} | Tier {p.tavern_tier}"
    else:
        label = f"P{p.player_id} — Eliminated #{p.finished_position}"

    with st.expander(label, expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("HP", p.health)
        c2.metric("Armor", p.armor)
        c3.metric("Tier", p.tavern_tier)
        c4.metric("Gold", f"{p.gold}/{p.gold_max}")

        # Show this turn's actions for this player
        if tlog:
            for pl in tlog.player_logs:
                if pl.player_id == p.player_id and pl.actions:
                    st.caption("This turn")
                    st.code(" > ".join(pl.actions), language=None)
                    if pl.shop_offered:
                        st.caption(f"Shop: {', '.join(pl.shop_offered)}")
                    break

        if p.board:
            st.caption("Board")
            _render_minion_table(p.board)

        if p.hand:
            st.caption("Hand")
            _render_minion_table(p.hand)

        if not p.board and not p.hand:
            st.caption("No minions")


def _render_minion_table(minions: tuple) -> None:
    rows = []
    for m in minions:
        name = m.name or m.card_id
        golden = "Yes" if m.golden else ""
        kw = []
        if m.taunt:
            kw.append("Taunt")
        if m.divine_shield:
            kw.append("DS")
        if m.poisonous:
            kw.append("Poison")
        if m.reborn:
            kw.append("Reborn")
        if m.windfury:
            kw.append("WF")
        rows.append({
            "Name": name,
            "Atk": m.attack,
            "HP": m.health,
            "Tier": m.tavern_tier,
            "Golden": golden,
            "Keywords": ", ".join(kw),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
