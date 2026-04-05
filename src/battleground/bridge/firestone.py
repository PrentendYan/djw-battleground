# -*- coding: utf-8 -*-
"""Python wrapper for the Firestone Node.js BG simulator bridge."""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from ..types import SimulationResult

logger = logging.getLogger(__name__)

_BRIDGE_JS = Path(__file__).parent / "bridge.js"
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # battleground/


class FirestoneError(Exception):
    """Error from the Firestone bridge."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


class FirestoneSimulator:
    """Python interface to the Firestone BG simulator via a persistent Node.js process.

    Usage::

        with FirestoneSimulator() as sim:
            result = sim.simulate(battle_info)
            print(result.summary())
    """

    MAX_RESTARTS = 3
    BACKOFF_BASE = 1.0  # seconds

    def __init__(
        self,
        node_path: str = "node",
        project_root: Path | None = None,
    ) -> None:
        self._node_path = node_path
        self._project_root = project_root or _PROJECT_ROOT
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._request_id = 0
        self._restart_count = 0
        self._stderr_thread: threading.Thread | None = None
        self._ready = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Node.js bridge process and wait for ready signal."""
        if self._process is not None and self._process.poll() is None:
            return  # Already running

        env_vars = {
            "BG_CACHE_DIR": str(self._project_root / "data"),
        }

        import os
        env = {**os.environ, **env_vars}

        self._process = subprocess.Popen(
            [self._node_path, str(_BRIDGE_JS)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self._project_root),
            env=env,
        )

        # Start stderr drain thread
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, daemon=True
        )
        self._stderr_thread.start()

        # Wait for ready signal
        ready_response = self._read_response(timeout=30.0)
        if ready_response.get("result", {}).get("ready"):
            card_count = ready_response["result"].get("card_count", "?")
            logger.info(f"Firestone bridge ready ({card_count} cards loaded)")
            self._ready = True
        else:
            raise FirestoneError("STARTUP_FAILED", f"Bridge did not signal ready: {ready_response}")

    def shutdown(self) -> None:
        """Gracefully stop the Node.js process and clean up all resources."""
        if self._process is None:
            return
        proc = self._process
        self._process = None
        self._ready = False
        try:
            # Try graceful shutdown
            proc.stdin.write(json.dumps({"id": 0, "method": "shutdown", "params": {}}).encode() + b"\n")
            proc.stdin.flush()
            proc.wait(timeout=5.0)
        except Exception:
            try:
                proc.terminate()
                proc.wait(timeout=3.0)
            except Exception:
                proc.kill()
        finally:
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if pipe:
                        pipe.close()
                except Exception:
                    pass

    def __enter__(self) -> FirestoneSimulator:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.shutdown()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        battle_info: dict,
        timeout: float = 15.0,
    ) -> SimulationResult:
        """Run a combat simulation and return aggregated results."""
        with self._lock:
            self._ensure_alive()
            response = self._call_locked("simulate", battle_info, timeout=timeout)
            return self._parse_simulation_result(response)

    def simulate_raw(
        self,
        battle_info: dict,
        timeout: float = 15.0,
    ) -> dict:
        """Run simulation and return raw Firestone result dict."""
        with self._lock:
            self._ensure_alive()
            return self._call_locked("simulate", battle_info, timeout=timeout)

    def get_card(self, card_id: str) -> dict:
        """Get card data by card ID."""
        with self._lock:
            self._ensure_alive()
            return self._call_locked("get_card", {"cardId": card_id})

    def get_bg_cards(self) -> list[dict]:
        """Get all Battlegrounds cards."""
        with self._lock:
            self._ensure_alive()
            return self._call_locked("get_bg_cards", {}, timeout=10.0)

    def refresh_cards(self) -> None:
        """Force refresh card data from remote."""
        with self._lock:
            self._ensure_alive()
            self._call_locked("refresh_cards", {}, timeout=30.0)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_alive(self) -> None:
        """Check if process is alive, restart if needed."""
        if self._process is not None and self._process.poll() is None:
            return

        if self._restart_count >= self.MAX_RESTARTS:
            raise FirestoneError(
                "MAX_RESTARTS",
                f"Bridge crashed {self.MAX_RESTARTS} times, giving up",
            )

        backoff = self.BACKOFF_BASE * (2 ** self._restart_count)
        logger.warning(f"Bridge process died, restarting in {backoff:.1f}s (attempt {self._restart_count + 1})")
        time.sleep(backoff)
        self._restart_count += 1
        self._process = None
        self.start()

    def _call_locked(self, method: str, params: dict, timeout: float = 10.0) -> Any:
        """Send request and wait for matching response. Caller must hold self._lock."""
        self._request_id += 1
        req_id = self._request_id
        self._send_request(method, params, req_id)
        response = self._read_response(timeout=timeout, expected_id=req_id)

        if response.get("error"):
            err = response["error"]
            raise FirestoneError(err.get("code", "UNKNOWN"), err.get("message", ""))

        return response.get("result")

    def _send_request(self, method: str, params: dict, req_id: int | None = None) -> None:
        """Write a JSON-line request to Node's stdin."""
        if req_id is None:
            self._request_id += 1
            req_id = self._request_id

        request = {"id": req_id, "method": method, "params": params}
        line = json.dumps(request) + "\n"
        try:
            self._process.stdin.write(line.encode("utf-8"))
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise FirestoneError("PIPE_ERROR", f"Failed to write to bridge: {e}")

    def _read_response(self, timeout: float = 10.0, expected_id: int | None = None) -> dict:
        """Read one JSON-line response from Node's stdout with timeout and id validation."""
        import select

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FirestoneError("TIMEOUT", f"No response within {timeout}s")

            # Use select for timeout on stdout
            ready, _, _ = select.select([self._process.stdout], [], [], min(remaining, 1.0))
            if ready:
                line = self._process.stdout.readline()
                if not line:
                    raise FirestoneError("EOF", "Bridge process closed stdout")
                decoded = line.decode("utf-8").strip()
                if not decoded:
                    continue
                # Skip non-JSON lines (e.g. npm/library log output)
                if not decoded.startswith("{"):
                    logger.debug(f"Skipping non-JSON stdout: {decoded}")
                    continue
                try:
                    parsed = json.loads(decoded)
                except json.JSONDecodeError:
                    logger.debug(f"Skipping malformed line: {decoded[:100]}")
                    continue

                # Validate response id matches request id (skip orphan responses)
                if expected_id is not None and parsed.get("id") != expected_id:
                    logger.warning(f"Discarding orphan response id={parsed.get('id')} (expected {expected_id})")
                    continue

                return parsed

            # Check if process died
            if self._process.poll() is not None:
                raise FirestoneError("PROCESS_DIED", f"Bridge exited with code {self._process.returncode}")

    def _drain_stderr(self) -> None:
        """Continuously read stderr to prevent buffer deadlock."""
        try:
            while self._process and self._process.poll() is None:
                line = self._process.stderr.readline()
                if line:
                    logger.debug(f"[bridge] {line.decode('utf-8', errors='replace').rstrip()}")
                else:
                    break
        except Exception:
            pass

    @staticmethod
    def _parse_simulation_result(raw: dict) -> SimulationResult:
        """Convert Firestone's raw result to our SimulationResult."""
        total_sims = raw.get("won", 0) + raw.get("tied", 0) + raw.get("lost", 0)
        if total_sims == 0:
            total_sims = 1

        # Firestone provides pre-computed averages and per-sim damage arrays.
        # damageWons/damageLosts may be empty; use averageDamageWon/Lost as fallback.
        win_damages = raw.get("damageWons") or []
        loss_damages = raw.get("damageLosts") or []

        result = SimulationResult(
            wins=raw.get("won", 0),
            losses=raw.get("lost", 0),
            ties=raw.get("tied", 0),
            total=total_sims,
            win_damages=win_damages,
            loss_damages=loss_damages,
        )

        # Store pre-computed averages from Firestone for accuracy
        result._firestone_avg_win_dmg = raw.get("averageDamageWon", 0.0)
        result._firestone_avg_loss_dmg = raw.get("averageDamageLost", 0.0)
        result._firestone_lethal_win = raw.get("wonLethalPercent", 0.0)
        result._firestone_lethal_loss = raw.get("lostLethalPercent", 0.0)

        return result

    # ------------------------------------------------------------------
    # Builder helpers for constructing battle input
    # ------------------------------------------------------------------

    @staticmethod
    def make_board_entity(
        card_id: str,
        attack: int,
        health: int,
        entity_id: int = 0,
        *,
        taunt: bool = False,
        divine_shield: bool = False,
        poisonous: bool = False,
        venomous: bool = False,
        reborn: bool = False,
        windfury: bool = False,
        cleave: bool = False,
        stealth: bool = False,
        friendly: bool = True,
        enchantments: list | None = None,
        tavern_tier: int | None = None,
    ) -> dict:
        """Build a BoardEntity dict for simulation input."""
        entity: dict[str, Any] = {
            "entityId": entity_id,
            "cardId": card_id,
            "attack": attack,
            "health": health,
            "friendly": friendly,
        }
        if taunt:
            entity["taunt"] = True
        if divine_shield:
            entity["divineShield"] = True
        if poisonous:
            entity["poisonous"] = True
        if venomous:
            entity["venomous"] = True
        if reborn:
            entity["reborn"] = True
        if windfury:
            entity["windfury"] = True
        if cleave:
            entity["cleave"] = True
        if stealth:
            entity["stealth"] = True
        if enchantments:
            entity["enchantments"] = enchantments
        if tavern_tier is not None:
            entity["tavernTier"] = tavern_tier
        return entity

    @staticmethod
    def make_battle_info(
        player_board: list[dict],
        opponent_board: list[dict],
        player_hero: str = "TB_BaconShop_HERO_01",
        opponent_hero: str = "TB_BaconShop_HERO_01",
        player_hp: int = 40,
        opponent_hp: int = 40,
        player_tier: int = 1,
        opponent_tier: int = 1,
        num_simulations: int = 10000,
        current_turn: int = 1,
    ) -> dict:
        """Build a BgsBattleInfo dict for simulation."""
        return {
            "playerBoard": {
                "player": {
                    "cardId": player_hero,
                    "hpLeft": player_hp,
                    "tavernTier": player_tier,
                    "heroPowers": [],
                    "questEntities": [],
                },
                "board": player_board,
            },
            "opponentBoard": {
                "player": {
                    "cardId": opponent_hero,
                    "hpLeft": opponent_hp,
                    "tavernTier": opponent_tier,
                    "heroPowers": [],
                    "questEntities": [],
                },
                "board": opponent_board,
            },
            "options": {
                "numberOfSimulations": num_simulations,
                "skipInfoLogs": True,
            },
            "gameState": {
                "currentTurn": current_turn,
                "validTribes": [],
                "anomalies": [],
            },
        }
