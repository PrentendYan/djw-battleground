# -*- coding: utf-8 -*-
"""Download BG card images from HearthstoneJSON CDN to local cache.

Strategy: try full card render first, fall back to 256x artwork.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_PATH = PROJECT_ROOT / "data" / "cards_cache.json"
IMG_DIR = PROJECT_ROOT / "data" / "card_images"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# CDN endpoints in priority order: full render → square artwork
ENDPOINTS = [
    ("render", "https://art.hearthstonejson.com/v1/render/latest/enUS/256x/{card_id}.png", ".png"),
    ("art", "https://art.hearthstonejson.com/v1/256x/{card_id}.jpg", "_art.jpg"),
]


def download_one(card_id: str) -> tuple[str, str]:
    """Download card image with fallback. Returns (card_id, result)."""
    # Check if any version already cached
    for _, _, suffix in ENDPOINTS:
        dest = IMG_DIR / f"{card_id}{suffix}"
        if dest.exists() and dest.stat().st_size > 1000:
            return card_id, "cached"

    # Try each endpoint
    for name, url_tmpl, suffix in ENDPOINTS:
        url = url_tmpl.format(card_id=card_id)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=15)
            data = resp.read()
            if len(data) < 1000:
                continue
            dest = IMG_DIR / f"{card_id}{suffix}"
            dest.write_bytes(data)
            return card_id, name
        except Exception:
            continue

    return card_id, "miss"


def main() -> None:
    if not CACHE_PATH.exists():
        print(f"Card cache not found: {CACHE_PATH}")
        sys.exit(1)

    with open(CACHE_PATH, encoding="utf-8") as f:
        all_cards = json.load(f)

    bg_cards = [
        c for c in all_cards
        if c.get("isBaconPool") and not c.get("premium") and c.get("type") == "Minion"
    ]
    card_ids = [c["id"] for c in bg_cards if c.get("id")]

    IMG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading images for {len(card_ids)} BG cards...")
    counts: dict[str, int] = {"render": 0, "art": 0, "cached": 0, "miss": 0}
    missed: list[str] = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(download_one, cid): cid for cid in card_ids}
        for i, future in enumerate(as_completed(futures), 1):
            cid, result = future.result()
            counts[result] = counts.get(result, 0) + 1
            if result == "miss":
                missed.append(cid)
            if i % 50 == 0 or i == len(card_ids):
                print(f"  [{i}/{len(card_ids)}] {counts}")

    print(f"\nDone: {counts}")
    if missed:
        manifest = IMG_DIR / "missing.txt"
        manifest.write_text("\n".join(sorted(missed)) + "\n")
        print(f"Missing IDs ({len(missed)}): {manifest}")
    else:
        missing_file = IMG_DIR / "missing.txt"
        if missing_file.exists():
            missing_file.unlink()
        print("All cards have images!")


if __name__ == "__main__":
    main()
