# -*- coding: utf-8 -*-
"""Card picker component — search and select BG minions from card database."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import streamlit as st


_PROJECT_ROOT = Path(__file__).parents[4]
_CACHE_PATH = _PROJECT_ROOT / "data" / "cards_cache.json"
_IMG_DIR = _PROJECT_ROOT / "data" / "card_images"
_CARD_IMG_URL = "https://art.hearthstonejson.com/v1/render/latest/enUS/256x/{card_id}.png"


@st.cache_data
def load_bg_cards() -> list[dict[str, Any]]:
    """Load BG pool minion cards from the local cache file."""
    bg_cards = [
        c for c in _load_all_cards()
        if c.get("isBaconPool") and not c.get("premium") and c.get("type") == "Minion"
    ]
    bg_cards.sort(key=lambda c: (c.get("techLevel", 0), c.get("name", "")))
    return bg_cards


def card_image_url(card_id: str) -> str:
    """Return the HearthstoneJSON CDN render URL for a card."""
    return _CARD_IMG_URL.format(card_id=card_id)


def card_image_local(card_id: str) -> Path | None:
    """Return the local image path if it exists, else None.

    Checks full render first, then tile art.
    """
    for suffix in ("_art.jpg", ".png"):
        path = _IMG_DIR / f"{card_id}{suffix}"
        if path.exists():
            return path
    return None


def render_card_image(
    card_id: str,
    card_name: str,
    *,
    use_container_width: bool = False,
    width: int | None = None,
) -> None:
    """Display a card image: local file if available, styled text fallback otherwise."""
    local = card_image_local(card_id)
    if local is not None:
        kwargs: dict[str, Any] = {}
        if use_container_width:
            kwargs["use_container_width"] = True
        elif width:
            kwargs["width"] = width
        st.image(str(local), **kwargs)
    else:
        safe_name = html.escape(card_name)
        st.markdown(
            f'<div style="text-align:center;padding:16px 4px;'
            f'border:1px solid #555;border-radius:8px;'
            f'background:#1a1a2e;color:#ccc;font-size:0.8em;">'
            f'{safe_name}</div>',
            unsafe_allow_html=True,
        )


@st.cache_data
def _load_all_cards() -> list[dict[str, Any]]:
    """Load the full card cache (memoised)."""
    if not _CACHE_PATH.exists():
        return []
    with open(_CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_bg_heroes() -> list[dict[str, Any]]:
    """Load BG heroes (battlegroundsHero=True) sorted by name."""
    cards = [
        c for c in _load_all_cards()
        if c.get("type") == "Hero"
        and "BG" in c.get("id", "")
        and not c.get("premium")
        and c.get("battlegroundsHero")
    ]
    cards.sort(key=lambda c: c.get("name", ""))
    return cards


@st.cache_data
def load_bg_hero_powers() -> list[dict[str, Any]]:
    """Load BG hero powers sorted by name."""
    cards = [
        c for c in _load_all_cards()
        if c.get("type") == "Hero_power" and "BG" in c.get("id", "")
    ]
    cards.sort(key=lambda c: c.get("name", ""))
    return cards


@st.cache_data
def load_bg_trinkets() -> list[dict[str, Any]]:
    """Load BG trinkets, sorted by tier then name."""
    cards = [
        c for c in _load_all_cards()
        if c.get("type") == "Battleground_trinket"
    ]
    tier_order = {"LESSER_TRINKET": 0, "GREATER_TRINKET": 1}
    cards.sort(key=lambda c: (tier_order.get(c.get("spellSchool", ""), 2), c.get("name", "")))
    return cards


@st.cache_data
def load_bg_anomalies() -> list[dict[str, Any]]:
    """Load BG anomalies sorted by name."""
    cards = [
        c for c in _load_all_cards()
        if c.get("type") == "Battleground_anomaly"
    ]
    cards.sort(key=lambda c: c.get("name", ""))
    return cards


@st.cache_data
def load_bg_spells() -> list[dict[str, Any]]:
    """Load BG tavern spells (includes secrets) sorted by name."""
    cards = [
        c for c in _load_all_cards()
        if c.get("type") == "Battleground_spell"
    ]
    cards.sort(key=lambda c: c.get("name", ""))
    return cards


@st.cache_data
def load_bg_quest_rewards() -> list[dict[str, Any]]:
    """Load BG quest rewards sorted by name."""
    cards = [
        c for c in _load_all_cards()
        if c.get("type") == "Battleground_quest_reward"
    ]
    cards.sort(key=lambda c: c.get("name", ""))
    return cards


def render_card_picker(
    key: str,
    label: str = "Select a minion",
) -> dict[str, Any] | None:
    """Render a card search/select widget. Returns selected card dict or None."""
    cards = load_bg_cards()
    if not cards:
        st.error(f"Card cache not found at {_CACHE_PATH}. Run the bridge once to generate it.")
        return None

    # All card_picker keys use _pick_ prefix to avoid collision with board_editor
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search = st.text_input(f"Search {label}", key=f"{key}_pick_search")
    with col2:
        tiers = sorted({c.get("techLevel", 0) for c in cards})
        tier_filter = st.selectbox(
            "Tier", [0] + tiers,
            format_func=lambda x: "All" if x == 0 else f"Tier {x}",
            key=f"{key}_pick_tier",
        )
    with col3:
        races = sorted({
            r for c in cards for r in (c.get("races") or [])
        })
        race_filter = st.selectbox("Race", ["All"] + races, key=f"{key}_pick_race")

    filtered = cards
    if search:
        search_lower = search.lower()
        filtered = [c for c in filtered if search_lower in c.get("name", "").lower() or search_lower in c.get("text", "").lower()]
    if tier_filter:
        filtered = [c for c in filtered if c.get("techLevel") == tier_filter]
    if race_filter != "All":
        filtered = [c for c in filtered if race_filter in (c.get("races") or [])]

    if not filtered:
        st.info("No matching cards.")
        return None

    card_options = {
        f"{c.get('name', '?')} ({c.get('attack', 0)}/{c.get('health', 0)}) T{c.get('techLevel', '?')}": c
        for c in filtered[:50]
    }
    selected_name = st.selectbox(label, list(card_options.keys()), key=f"{key}_pick_select")

    if not selected_name:
        return None

    card = card_options[selected_name]
    card_id = card.get("id", "")
    if card_id:
        render_card_image(card_id, card.get("name", card_id), width=180)
    return card
