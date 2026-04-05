# -*- coding: utf-8 -*-
"""Battleground Simulator — Streamlit main application.

Run with:
    streamlit run src/battleground/ui/app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="BG Simulator",
    page_icon="⚔️",
    layout="wide",
)

from battleground.bridge.firestone import FirestoneSimulator  # noqa: E402
from battleground.game.state import PlayerState  # noqa: E402
from battleground.game.battle_api import BattleAPI  # noqa: E402
from battleground.ui.components.board_editor import (  # noqa: E402
    hero_hp_key,
    hero_power_key,
    hero_select_key,
    hero_tier_key,
    quest_key,
    render_board_visual,
    secrets_key,
)
from battleground.ui.components.card_picker import (  # noqa: E402
    load_bg_anomalies,
    load_bg_hero_powers,
    load_bg_heroes,
    load_bg_quest_rewards,
    load_bg_spells,
    load_bg_trinkets,
)
from battleground.ui.components.results import render_results  # noqa: E402
from battleground.ui.components.simulation_viewer import (  # noqa: E402
    render_simulation_main,
    render_simulation_sidebar,
)


# ---------------------------------------------------------------------------
# Session state: persistent Firestone simulator
# ---------------------------------------------------------------------------

def _get_simulator() -> FirestoneSimulator:
    """Get or create the shared FirestoneSimulator instance."""
    if "simulator" not in st.session_state:
        sim = FirestoneSimulator()
        sim.start()
        st.session_state["simulator"] = sim
    return st.session_state["simulator"]


def _get_battle_api() -> BattleAPI:
    """Get or create the BattleAPI instance."""
    if "battle_api" not in st.session_state:
        st.session_state["battle_api"] = BattleAPI(_get_simulator())
    return st.session_state["battle_api"]


# ---------------------------------------------------------------------------
# Helpers: resolve S6 card names → cardId dicts for Firestone
# ---------------------------------------------------------------------------

def _resolve_hero_card_id(side: str) -> str:
    """Resolve selected hero name to card ID."""
    selected = st.session_state.get(hero_select_key(side), "(none)")
    if selected == "(none)":
        return "TB_BaconShop_HERO_01"  # default Bob
    hero_by_name = {c.get("name", ""): c for c in load_bg_heroes()}
    if selected in hero_by_name:
        return hero_by_name[selected]["id"]
    return "TB_BaconShop_HERO_01"


def _resolve_global_info(side: str) -> dict | None:
    """Resolve global info fields from session_state."""
    ek = st.session_state.get(f"{side}_gi_eternalKnightDead", 0)
    pa = st.session_state.get(f"{side}_gi_pirateAttackBonus", 0)
    bg_atk = st.session_state.get(f"{side}_gi_bloodGemAtk", 1)
    bg_hp = bg_atk  # blood gem health usually matches attack
    if ek == 0 and pa == 0 and bg_atk == 1:
        return None  # no custom global info
    return {
        "EternalKnightsDeadThisGame": int(ek),
        "PiratesPlayedThisGame": int(pa),
        "BloodGemAttackBonus": int(bg_atk),
        "BloodGemHealthBonus": int(bg_hp),
    }


def _resolve_hero_powers(side: str) -> tuple[dict, ...]:
    """Resolve selected hero power names (up to 2) to Firestone heroPower dicts."""
    hp_by_name = {c.get("name", ""): c for c in load_bg_hero_powers()}
    result: list[dict] = []
    for idx in range(2):
        selected = st.session_state.get(hero_power_key(side, idx), "(none)")
        if selected != "(none)" and selected in hp_by_name:
            result.append({"cardId": hp_by_name[selected]["id"], "isPassive": True})
    return tuple(result)


def _resolve_quest(side: str) -> tuple[dict, ...]:
    """Resolve selected quest reward to Firestone questEntities dict."""
    selected = st.session_state.get(quest_key(side), "(none)")
    if selected == "(none)":
        return ()
    quest_by_name = {c.get("name", ""): c for c in load_bg_quest_rewards()}
    if selected in quest_by_name:
        return ({"cardId": quest_by_name[selected]["id"]},)
    return ()


def _resolve_trinkets(side: str) -> tuple[dict, ...]:
    """Resolve selected trinkets to Firestone trinket dicts."""
    all_trinkets = load_bg_trinkets()
    trinket_by_name = {c.get("name", ""): c for c in all_trinkets}
    result: list[dict] = []
    for tier_key in (f"{side}_trinket_lesser", f"{side}_trinket_greater"):
        name = st.session_state.get(tier_key, "(none)")
        if name != "(none)" and name in trinket_by_name:
            result.append({"cardId": trinket_by_name[name]["id"]})
    return tuple(result)


def _resolve_secrets(side: str) -> tuple[dict, ...]:
    """Resolve selected secrets to Firestone secret dicts."""
    selected_names = st.session_state.get(secrets_key(side), [])
    if not selected_names:
        return ()
    spell_by_name = {c.get("name", ""): c for c in load_bg_spells()}
    return tuple(
        {"cardId": spell_by_name[n]["id"]}
        for n in selected_names
        if n in spell_by_name
    )


def _resolve_anomalies() -> tuple[str, ...]:
    """Resolve selected anomaly names to cardId strings."""
    selected_names = st.session_state.get("anomaly_select", [])
    if not selected_names:
        return ()
    anomaly_by_name = {c.get("name", ""): c for c in load_bg_anomalies()}
    return tuple(
        anomaly_by_name[n]["id"]
        for n in selected_names
        if n in anomaly_by_name
    )


# ---------------------------------------------------------------------------
# Sidebar: mode selector
# ---------------------------------------------------------------------------

with st.sidebar:
    app_mode = st.radio("Mode", ["Battle Simulator", "Game Simulation"], key="app_mode")

# ---------------------------------------------------------------------------
# Mode: Game Simulation
# ---------------------------------------------------------------------------

if app_mode == "Game Simulation":
    with st.sidebar:
        render_simulation_sidebar()

    st.title("Battleground Simulation")
    render_simulation_main()

# ---------------------------------------------------------------------------
# Mode: Battle Simulator (original)
# ---------------------------------------------------------------------------

else:
    with st.sidebar:
        st.header("Settings")
        num_sims = st.slider("Simulations", 100, 50000, 10000, step=100, key="sim_count")
        current_turn = st.number_input("Current Turn", 1, 50, 1, key="sim_turn")

        st.header("Anomalies")
        anomaly_names = [c.get("name", "?") for c in load_bg_anomalies()]
        st.multiselect("Active Anomalies", anomaly_names, key="anomaly_select", label_visibility="collapsed")

    st.title("Battleground Simulator")

    # Opponent board (top)
    st.markdown("---")
    opponent_minions, opponent_hand = render_board_visual("Opponent")

    # VS divider
    st.markdown(
        "<div style='text-align:center;font-size:2em;margin:0.5em 0;'>VS</div>",
        unsafe_allow_html=True,
    )

    # Player board (bottom)
    player_minions, player_hand = render_board_visual("Player")
    st.markdown("---")

    # Simulate button
    if st.button("Simulate Combat", type="primary", use_container_width=True, key="sim_button"):
        if not player_minions and not opponent_minions:
            st.warning("Add at least one minion to either board.")
        else:
            anomalies = _resolve_anomalies()

            def _build_player_state(
                side: str, pid: int, minions: list, hand: list,
            ) -> PlayerState:
                from battleground.game.state import HeroState
                return PlayerState(
                    player_id=pid,
                    health=int(st.session_state.get(hero_hp_key(side), 40)),
                    armor=int(st.session_state.get(f"{side}_hero_armor", 0)),
                    tavern_tier=int(st.session_state.get(hero_tier_key(side), 1)),
                    hero=HeroState(card_id=_resolve_hero_card_id(side)),
                    board=tuple(minions),
                    hand=tuple(hand),
                    hero_powers=_resolve_hero_powers(side),
                    trinkets=_resolve_trinkets(side),
                    secrets=_resolve_secrets(side),
                    quest_entities=_resolve_quest(side),
                    global_info=_resolve_global_info(side),
                )

            player = _build_player_state("Player", 0, player_minions, player_hand)
            opponent = _build_player_state("Opponent", 1, opponent_minions, opponent_hand)

            with st.spinner("Running simulation..."):
                try:
                    api = _get_battle_api()
                    result = api.run_combat(
                        player,
                        opponent,
                        num_simulations=num_sims,
                        current_turn=int(current_turn),
                        anomalies=anomalies,
                    )
                    render_results(result)
                except Exception as e:
                    st.error(f"Simulation failed: {e}")
