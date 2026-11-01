"""Konfigurasi model per tier (config/tiers.json).

Ditulis dashboard (PUT /api/tiers), dibaca router tiap request (cache per mtime),
sehingga ganti model tidak perlu restart. Kalau file tidak ada atau tidak valid,
kembali ke nilai .env yang dikirim pemanggil.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

TIERS_PATH = Path(__file__).resolve().parent.parent / "config" / "tiers.json"
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,100}$")  # validasi F4 (PRD)

_cache: tuple[int, dict | None] | None = None


def load_tiers() -> dict | None:
    """Baca config/tiers.json, cache berdasarkan mtime. None kalau tidak ada/rusak."""
    global _cache
    try:
        mtime = TIERS_PATH.stat().st_mtime_ns
    except OSError:
        return None
    if _cache is None or _cache[0] != mtime:
        data: dict | None = None
        try:
            parsed = json.loads(TIERS_PATH.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, ValueError):
            pass
        _cache = (mtime, data)
    return _cache[1]


def current_models(light_env: str, heavy_env: str) -> tuple[str, str]:
    """Model aktif: config/tiers.json bila valid, selain itu fallback .env."""
    data = load_tiers() or {}
    light, heavy = data.get("light"), data.get("heavy")
    if not (isinstance(light, str) and MODEL_RE.fullmatch(light)):
        light = light_env
    if not (isinstance(heavy, str) and MODEL_RE.fullmatch(heavy)):
        heavy = heavy_env
    return light, heavy


def save_tiers(light: str, heavy: str) -> None:
    """Tulis config/tiers.json secara atomik (file sementara lalu os.replace)."""
    TIERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TIERS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"light": light, "heavy": heavy}), encoding="utf-8")
    os.replace(tmp, TIERS_PATH)
    load_tiers()  # segarkan cache supaya request berikutnya langsung pakai nilai baru
