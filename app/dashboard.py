"""Login dashboard (F1): password di-hash scrypt, disimpan di config/dashboard.json.

Pakai (jalankan sendiri di terminal, password diketik lewat getpass):
    python -m app.dashboard set-password
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from collections import deque
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

HASH_PATH = Path(__file__).resolve().parent.parent / "config" / "dashboard.json"
SESSION_TTL = 12 * 3600
COOKIE = "dash_session"
MAX_FAILS, FAIL_WINDOW = 5, 300  # ponytail: rate limit global, bukan per IP (cukup untuk satu pemilik)

_sessions: dict[str, float] = {}
_fails: deque[float] = deque()

router = APIRouter(prefix="/api")


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=len(dk) // 2)
    except ValueError:
        return False
    return hmac.compare_digest(got.hex(), dk)


def stored_hash() -> str | None:
    try:
        return json.loads(HASH_PATH.read_text(encoding="utf-8")).get("password_hash")
    except (OSError, ValueError):
        return None


def password_configured() -> bool:
    return bool(stored_hash())


def save_hash(h: str) -> None:
    HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HASH_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"password_hash": h}), encoding="utf-8")
    os.replace(tmp, HASH_PATH)


def same_origin(request: Request) -> bool:
    """Anti-CSRF: Origin harus sama dengan Host tempat dashboard disajikan."""
    origin = request.headers.get("origin", "")
    return bool(origin) and urlsplit(origin).netloc == request.headers.get("host", "")


def require_session(request: Request) -> None:
    token = request.cookies.get(COOKIE, "")
    exp = _sessions.get(token)
    if not exp or exp < time.time():
        _sessions.pop(token, None)
        raise HTTPException(401, "Belum login")


class LoginBody(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginBody, request: Request):
    if not same_origin(request):
        raise HTTPException(403, "Origin tidak diizinkan")
    now = time.time()
    while _fails and now - _fails[0] > FAIL_WINDOW:
        _fails.popleft()
    if len(_fails) >= MAX_FAILS:
        raise HTTPException(429, "Terlalu banyak percobaan. Coba lagi beberapa menit.")
    stored = stored_hash()
    if not stored:
        raise HTTPException(503, "Password dashboard belum diset (python -m app.dashboard set-password)")
    if not verify_password(body.password, stored):
        _fails.append(now)
        raise HTTPException(401, "Password salah")
    _fails.clear()
    token = secrets.token_urlsafe(32)
    _sessions[token] = now + SESSION_TTL
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, token, max_age=SESSION_TTL, httponly=True, samesite="strict", path="/")
    return resp


@router.post("/logout")
async def logout(request: Request):
    if not same_origin(request):
        raise HTTPException(403, "Origin tidak diizinkan")
    _sessions.pop(request.cookies.get(COOKIE, ""), None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE, path="/")
    return resp


@router.get("/session", dependencies=[Depends(require_session)])
async def session_info():
    return {"ok": True}


def _set_password_cli() -> int:
    pw = getpass("Password dashboard baru (min 8 karakter): ")
    if len(pw) < 8:
        print("Terlalu pendek.")
        return 1
    if pw != getpass("Ulangi password: "):
        print("Tidak sama.")
        return 1
    save_hash(hash_password(pw))
    print(f"Hash tersimpan di {HASH_PATH}. Restart router agar dashboard aktif.")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] != ["set-password"]:
        print("Pakai: python -m app.dashboard set-password")
        sys.exit(2)
    sys.exit(_set_password_cli())
