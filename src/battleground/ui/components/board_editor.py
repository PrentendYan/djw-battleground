# -*- coding: utf-8 -*-
"""Board editor component — visual 7-slot board layout like the game."""

from __future__ import annotations

from typing import Any

import streamlit as st

from battleground.game.state import MinionState
from battleground.ui.components.card_picker import (
    load_bg_cards,
    load_bg_hero_powers,
    load_bg_heroes,
    load_bg_quest_rewards,
    load_bg_spells,
    load_bg_trinkets,
    render_card_image,
)


# --- Single source of truth for keyword names and their mechanic mappings ---

_KEYWORD_NAMES: tuple[str, ...] = (
    "taunt", "divine_shield", "poisonous", "reborn",
    "windfury", "venomous", "cleave", "stealth",
)

_MECHANIC_MAP: dict[str, str] = {
    "taunt": "TAUNT",
    "divine_shield": "DIVINE_SHIELD",
    "poisonous": "POISONOUS",
    "reborn": "REBORN",
    "windfury": "WINDFURY",
    "stealth": "STEALTH",
}

_IMG_SIZE = 64  # consistent icon size for hero power / trinkets / quest


# --- Shared key helpers (used by app.py to read hero state) ---

def hero_select_key(side: str) -> str:
    return f"{side}_hero_select"


def hero_hp_key(side: str) -> str:
    return f"{side}_hero_hp"


def hero_tier_key(side: str) -> str:
    return f"{side}_hero_tier"


def hero_power_key(side: str, idx: int = 0) -> str:
    return f"{side}_hero_power_{idx}"


def quest_key(side: str) -> str:
    return f"{side}_quest"


def trinkets_key(side: str) -> str:
    return f"{side}_trinkets"


def secrets_key(side: str) -> str:
    return f"{side}_secrets"


def _on_card_change(slot_key: str) -> None:
    """Reset stat overrides and keyword toggles when card selection changes."""
    for suffix in ("_atk", "_hp"):
        k = f"{slot_key}{suffix}"
        if k in st.session_state:
            del st.session_state[k]
    for kw in _KEYWORD_NAMES:
        k = f"{slot_key}_kw_{kw}"
        if k in st.session_state:
            del st.session_state[k]


def render_board_visual(
    side: str,
    max_minions: int = 7,
) -> tuple[list[MinionState], list[MinionState]]:
    """Render a visual board with 7 minion slots + hand editor.

    Returns (board_minions, hand_minions).
    """
    cards_db = load_bg_cards()
    if not cards_db:
        st.warning("Card database not loaded.")
        return [], []

    # Build card lookup by name for the selectbox (with duplicate guard)
    card_by_name: dict[str, dict[str, Any]] = {}
    for c in cards_db:
        display = f"{c.get('name', '?')} (T{c.get('techLevel', '?')})"
        if display not in card_by_name:
            card_by_name[display] = c
    card_names = ["(empty)"] + list(card_by_name.keys())

    # Hero info bar — game-style layout
    _render_hero_bar(side)

    # 7 minion slots in a row
    cols = st.columns(max_minions)
    minions: list[MinionState] = []

    for i in range(max_minions):
        with cols[i]:
            minion = _render_slot(side, i, card_names, card_by_name)
            if minion is not None:
                minions.append(minion)

    # Hand editor
    hand = _render_hand_editor(side, card_names, card_by_name)

    return minions, hand


# ---------------------------------------------------------------------------
# Hero bar: [Trinkets] [Hero portrait + stats] [Hero Powers + Quest]
# ---------------------------------------------------------------------------

def _render_hero_bar(side: str) -> None:
    """Render hero info in game-like layout: trinkets left, hero center, powers right."""
    # Load data
    heroes = load_bg_heroes()
    hero_names = ["(none)"] + [c.get("name", "?") for c in heroes]
    hero_by_name = {c.get("name", ""): c for c in heroes}

    all_trinkets = load_bg_trinkets()
    lesser = [c for c in all_trinkets if c.get("spellSchool") == "LESSER_TRINKET"]
    greater = [c for c in all_trinkets if c.get("spellSchool") == "GREATER_TRINKET"]
    trinket_by_name = {c.get("name", ""): c for c in all_trinkets}

    hero_powers = load_bg_hero_powers()
    hp_names = ["(none)"] + [c.get("name", "?") for c in hero_powers]
    hp_by_name = {c.get("name", ""): c for c in hero_powers}

    quest_rewards = load_bg_quest_rewards()
    quest_names = ["(none)"] + [c.get("name", "?") for c in quest_rewards]
    quest_by_name = {c.get("name", ""): c for c in quest_rewards}

    # Layout: trinket_imgs | trinket_sel | hero_portrait | hero_stats | power_sel | power_imgs
    col_ti, col_ts, col_portrait, col_stats, col_ps, col_pi = st.columns(
        [0.8, 2, 1, 1.5, 2, 0.8]
    )

    # --- LEFT: Trinket images ---
    with col_ti:
        sel_l = st.session_state.get(f"{side}_trinket_lesser", "(none)")
        if sel_l != "(none)" and sel_l in trinket_by_name:
            render_card_image(trinket_by_name[sel_l]["id"], sel_l, width=_IMG_SIZE)
        sel_g = st.session_state.get(f"{side}_trinket_greater", "(none)")
        if sel_g != "(none)" and sel_g in trinket_by_name:
            render_card_image(trinket_by_name[sel_g]["id"], sel_g, width=_IMG_SIZE)

    # --- LEFT: Trinket selectors ---
    with col_ts:
        st.selectbox("Lesser Trinket", ["(none)"] + [c.get("name", "?") for c in lesser],
                     key=f"{side}_trinket_lesser", label_visibility="collapsed")
        st.selectbox("Greater Trinket", ["(none)"] + [c.get("name", "?") for c in greater],
                     key=f"{side}_trinket_greater", label_visibility="collapsed")

    # --- CENTER: Hero portrait ---
    with col_portrait:
        sel_hero = st.session_state.get(hero_select_key(side), "(none)")
        if sel_hero != "(none)" and sel_hero in hero_by_name:
            render_card_image(hero_by_name[sel_hero]["id"], sel_hero, width=80)
        else:
            st.markdown(
                f"<div style='width:80px;height:80px;border:2px solid #555;"
                f"border-radius:50%;display:flex;align-items:center;"
                f"justify-content:center;color:#888;font-size:0.7em;'>"
                f"{side}</div>",
                unsafe_allow_html=True,
            )

    # --- CENTER: Hero stats ---
    with col_stats:
        st.selectbox("Hero", hero_names, key=hero_select_key(side),
                     label_visibility="collapsed")
        # Auto-fill armor from hero data
        hero_data = hero_by_name.get(
            st.session_state.get(hero_select_key(side), "(none)"), {}
        )
        default_armor = hero_data.get("armor", 0)

        h1, h2, h3 = st.columns(3)
        with h1:
            st.number_input("HP", value=40, min_value=1, max_value=100,
                            key=hero_hp_key(side))
        with h2:
            st.number_input("Armor", value=default_armor, min_value=0, max_value=50,
                            key=f"{side}_hero_armor")
        with h3:
            st.number_input("Tier", value=1, min_value=1, max_value=6,
                            key=hero_tier_key(side))

    # --- RIGHT: Hero Power + Quest selectors ---
    with col_ps:
        st.selectbox("Hero Power 1", hp_names, key=hero_power_key(side, 0),
                     label_visibility="collapsed")
        st.selectbox("Hero Power 2", hp_names, key=hero_power_key(side, 1),
                     label_visibility="collapsed")
        st.selectbox("Quest Reward", quest_names, key=quest_key(side),
                     label_visibility="collapsed")

    # --- RIGHT: Hero Power + Quest images ---
    with col_pi:
        for idx in range(2):
            sel = st.session_state.get(hero_power_key(side, idx), "(none)")
            if sel != "(none)" and sel in hp_by_name:
                render_card_image(hp_by_name[sel]["id"], sel, width=_IMG_SIZE)
        sel_q = st.session_state.get(quest_key(side), "(none)")
        if sel_q != "(none)" and sel_q in quest_by_name:
            render_card_image(quest_by_name[sel_q]["id"], sel_q, width=_IMG_SIZE)

    # --- Extras: Secrets + Global Info ---
    with st.expander(f"Secrets & Global Info ({side})", expanded=False):
        spells = load_bg_spells()
        spell_names = [c.get("name", "?") for c in spells]
        st.multiselect("Secrets / Spells", spell_names, key=secrets_key(side),
                       label_visibility="collapsed")
        st.caption("Global Info")
        gi1, gi2, gi3 = st.columns(3)
        with gi1:
            st.number_input("Eternal Knight Deaths", value=0, min_value=0,
                            key=f"{side}_gi_eternalKnightDead")
        with gi2:
            st.number_input("Pirate Atk Bonus", value=0, min_value=0,
                            key=f"{side}_gi_pirateAttackBonus")
        with gi3:
            st.number_input("Blood Gem Atk", value=1, min_value=1,
                            key=f"{side}_gi_bloodGemAtk")


# ---------------------------------------------------------------------------
# Minion slot
# ---------------------------------------------------------------------------

def _render_slot(
    side: str,
    idx: int,
    card_names: list[str],
    card_by_name: dict[str, dict[str, Any]],
) -> MinionState | None:
    """Render a single minion slot with card image and stat overrides."""
    key = f"{side}_s{idx}"

    selected = st.selectbox(
        f"Slot {idx + 1}",
        card_names,
        key=f"{key}_card",
        label_visibility="collapsed",
        on_change=_on_card_change,
        args=(key,),
    )

    if selected == "(empty)":
        st.markdown(
            "<div style='height:120px;border:1px dashed #555;border-radius:8px;"
            "display:flex;align-items:center;justify-content:center;color:#666;'>"
            "Empty</div>",
            unsafe_allow_html=True,
        )
        return None

    card = card_by_name[selected]
    card_id = card.get("id", "")

    # Show card image (local file or text fallback)
    card_name = card.get("name", "?")
    if card_id:
        render_card_image(card_id, card_name, use_container_width=True)
    else:
        st.caption(card_name)

    # Compact stat overrides
    a_col, h_col = st.columns(2)
    with a_col:
        attack = st.number_input(
            "Atk", value=card.get("attack", 1),
            min_value=0, max_value=999,
            key=f"{key}_atk", label_visibility="collapsed",
        )
    with h_col:
        health = st.number_input(
            "HP", value=card.get("health", 1),
            min_value=1, max_value=999,
            key=f"{key}_hp", label_visibility="collapsed",
        )

    # Keywords — derived from _KEYWORD_NAMES (single source of truth)
    mechanics = card.get("mechanics") or []
    kw_defaults = {
        kw: _MECHANIC_MAP.get(kw, "") in mechanics if _MECHANIC_MAP.get(kw) else False
        for kw in _KEYWORD_NAMES
    }

    # Show active keywords as badges
    active_kw = [k for k, v in kw_defaults.items() if v]
    if active_kw:
        st.caption(" ".join(k.upper()[:2] for k in active_kw))

    keywords: dict[str, bool] = {}
    with st.popover("Keywords", use_container_width=True):
        for kw_name, default in kw_defaults.items():
            keywords[kw_name] = st.checkbox(
                kw_name.replace("_", " ").title(),
                value=default,
                key=f"{key}_kw_{kw_name}",
            )

    # Explicit keyword args — no **spread, type-safe
    return MinionState(
        card_id=card_id,
        name=card_name,
        attack=int(attack),
        health=int(health),
        tavern_tier=card.get("techLevel", 1),
        taunt=keywords["taunt"],
        divine_shield=keywords["divine_shield"],
        poisonous=keywords["poisonous"],
        reborn=keywords["reborn"],
        windfury=keywords["windfury"],
        venomous=keywords["venomous"],
        cleave=keywords["cleave"],
        stealth=keywords["stealth"],
    )


# ---------------------------------------------------------------------------
# Hand editor — compact row inside an expander
# ---------------------------------------------------------------------------

_MAX_HAND = 10


def _render_hand_editor(
    side: str,
    card_names: list[str],
    card_by_name: dict[str, dict[str, Any]],
) -> list[MinionState]:
    """Render a compact hand editor in a collapsible panel. Returns list of MinionState."""
    hand: list[MinionState] = []
    num_key = f"{side}_hand_num"
    with st.expander(f"Hand ({side})", expanded=False):
        num = st.number_input(
            "Cards in hand", value=0, min_value=0, max_value=_MAX_HAND,
            key=num_key,
        )
        if num == 0:
            return hand
        cols = st.columns(min(int(num), 5))
        for i in range(int(num)):
            with cols[i % 5]:
                minion = _render_hand_slot(side, i, card_names, card_by_name)
                if minion is not None:
                    hand.append(minion)
    return hand


def _render_hand_slot(
    side: str,
    idx: int,
    card_names: list[str],
    card_by_name: dict[str, dict[str, Any]],
) -> MinionState | None:
    """Render a single compact hand card slot."""
    key = f"{side}_h{idx}"

    selected = st.selectbox(
        f"Hand {idx + 1}",
        card_names,
        key=f"{key}_card",
        label_visibility="collapsed",
        on_change=_on_card_change,
        args=(key,),
    )

    if selected == "(empty)":
        return None

    card = card_by_name[selected]
    card_id = card.get("id", "")
    card_name = card.get("name", "?")

    if card_id:
        render_card_image(card_id, card_name, width=80)

    a_col, h_col = st.columns(2)
    with a_col:
        attack = st.number_input(
            "Atk", value=card.get("attack", 1),
            min_value=0, max_value=999,
            key=f"{key}_atk", label_visibility="collapsed",
        )
    with h_col:
        health = st.number_input(
            "HP", value=card.get("health", 1),
            min_value=1, max_value=999,
            key=f"{key}_hp", label_visibility="collapsed",
        )

    mechanics = card.get("mechanics") or []
    kw_defaults = {
        kw: _MECHANIC_MAP.get(kw, "") in mechanics if _MECHANIC_MAP.get(kw) else False
        for kw in _KEYWORD_NAMES
    }

    active_kw = [k for k, v in kw_defaults.items() if v]
    if active_kw:
        st.caption(" ".join(k.upper()[:2] for k in active_kw))

    keywords: dict[str, bool] = {}
    with st.popover("Keywords", use_container_width=True):
        for kw_name, default in kw_defaults.items():
            keywords[kw_name] = st.checkbox(
                kw_name.replace("_", " ").title(),
                value=default,
                key=f"{key}_kw_{kw_name}",
            )

    return MinionState(
        card_id=card_id,
        name=card_name,
        attack=int(attack),
        health=int(health),
        tavern_tier=card.get("techLevel", 1),
        taunt=keywords["taunt"],
        divine_shield=keywords["divine_shield"],
        poisonous=keywords["poisonous"],
        reborn=keywords["reborn"],
        windfury=keywords["windfury"],
        venomous=keywords["venomous"],
        cleave=keywords["cleave"],
        stealth=keywords["stealth"],
    )
