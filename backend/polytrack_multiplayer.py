"""Ephemeral multiplayer rooms for Poly Track."""
from __future__ import annotations
import secrets
import threading
import time
from typing import Any

_LOCK = threading.RLock()
_ROOMS: dict[str, dict[str, Any]] = {}
_MAX_PLAYERS = 8
_IDLE_SECONDS = 45
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def _name(value: str) -> str:
    return " ".join(str(value or "").split())[:18] or "Spieler"

def _cleanup() -> None:
    now = time.time()
    for code in list(_ROOMS):
        room = _ROOMS[code]
        for pid in list(room["players"]):
            if now - room["players"][pid]["lastSeen"] > _IDLE_SECONDS:
                del room["players"][pid]
        if not room["players"] or now - room["createdAt"] > 8 * 60 * 60:
            del _ROOMS[code]

def _snapshot(room: dict[str, Any]) -> dict[str, Any]:
    return {"code": room["code"], "players": [
        {"id": p["id"], "name": p["name"], "position": p.get("position"),
         "isHost": p["id"] == room["hostId"]}
        for p in room["players"].values()
    ], "maxPlayers": _MAX_PLAYERS}

def create_room(name: str) -> dict[str, Any]:
    with _LOCK:
        _cleanup()
        code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        while code in _ROOMS:
            code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        pid = secrets.token_urlsafe(18)
        now = time.time()
        room = {"code": code, "createdAt": now, "hostId": pid,
                "players": {pid: {"id": pid, "name": _name(name), "lastSeen": now, "position": None}}}
        _ROOMS[code] = room
        return {**_snapshot(room), "playerId": pid}

def join_room(code: str, name: str) -> dict[str, Any]:
    code = str(code or "").strip().upper()
    with _LOCK:
        _cleanup()
        room = _ROOMS.get(code)
        if not room:
            raise ValueError("Raum nicht gefunden oder abgelaufen.")
        if len(room["players"]) >= _MAX_PLAYERS:
            raise ValueError("Der Raum ist voll.")
        pid = secrets.token_urlsafe(18)
        room["players"][pid] = {"id": pid, "name": _name(name), "lastSeen": time.time(), "position": None}
        return {**_snapshot(room), "playerId": pid}

def get_room(code: str) -> dict[str, Any] | None:
    with _LOCK:
        _cleanup()
        room = _ROOMS.get(str(code or "").strip().upper())
        return _snapshot(room) if room else None

def heartbeat_player(code: str, player_id: str, position: Any) -> dict[str, Any]:
    with _LOCK:
        _cleanup()
        room = _ROOMS.get(str(code or "").strip().upper())
        player = room["players"].get(player_id) if room else None
        if not player:
            raise ValueError("Spieler oder Raum nicht gefunden. Bitte erneut beitreten.")
        if position is not None:
            if not isinstance(position, dict) or len(position) > 20:
                raise ValueError("Ungültige Positionsdaten.")
            player["position"] = position
        player["lastSeen"] = time.time()
        return _snapshot(room)

def leave_player(code: str, player_id: str) -> dict[str, Any]:
    with _LOCK:
        room = _ROOMS.get(str(code or "").strip().upper())
        if room and player_id in room["players"]:
            del room["players"][player_id]
            if not room["players"]:
                del _ROOMS[room["code"]]
        return {"ok": True}
