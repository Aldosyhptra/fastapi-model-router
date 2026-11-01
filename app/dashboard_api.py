"""API dashboard (F2-F5): ringkasan, monitor, status, ganti model per tier.

Semua endpoint butuh sesi login (F1, lihat app.dashboard). Data dibaca dari
logs/decisions.jsonl; field cost dan cached_tokens bisa kosong → dikirim apa
adanya, frontend yang menampilkan "n/a".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import tiers as tiers_cfg
from .dashboard import require_session, same_origin

LOG_PATH = Path(os.environ.get("LOG_PATH", "logs/decisions.jsonl"))
LIGHT_MODEL = os.environ.get("LIGHT_MODEL", "deepseek-v4-flash")
HEAVY_MODEL = os.environ.get("HEAVY_MODEL", "deepseek-v4-pro")
WINDOWS = {"1h": 3600, "24h": 86400, "all": None}

router = APIRouter(prefix="/api", dependencies=[Depends(require_session)])


def _read_rows() -> list[dict]:
    """Baca semua baris decisions.jsonl. File milik sendiri, skala MB — ponytail:
    parse ulang penuh tiap request; kalau log >100MB, ganti ke ringkas inkremental."""
    rows: list[dict] = []
    try:
        with LOG_PATH.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue  # baris rusak dilewati, tidak boleh mematikan halaman
    except OSError:
        pass  # log belum ada → ringkasan kosong
    return rows


@router.get("/summary")
async def summary(window: str = "24h"):
    if window not in WINDOWS:
        raise HTTPException(400, "window harus 1h, 24h, atau all")
    rows = _read_rows()
    if WINDOWS[window] is not None:
        import time
        cutoff = time.time() - WINDOWS[window]
        rows = [r for r in rows if r.get("ts", 0) >= cutoff]

    total = len(rows)
    per_tier: dict[str, int] = {}
    prompt = cached = completion = 0
    cost = 0.0
    no_cost = 0
    latencies: list[int] = []
    for r in rows:
        per_tier[r.get("tier", "?")] = per_tier.get(r.get("tier", "?"), 0) + 1
        u = r.get("usage") or {}
        prompt += u.get("prompt_tokens") or 0
        completion += u.get("completion_tokens") or 0
        cached += (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        if u.get("cost") is not None:
            cost += u["cost"]
        elif u:
            no_cost += 1
        if r.get("latency_ms") is not None:
            latencies.append(r["latency_ms"])
    latencies.sort()
    return {
        "window": window,
        "total": total,
        "per_tier": per_tier,
        "prompt_tokens": prompt,
        "cached_tokens": cached,
        "completion_tokens": completion,
        "cache_ratio": (cached / prompt) if prompt else None,
        "cost_usd": cost,
        "rows_without_cost": no_cost,
        "latency_p50_ms": latencies[len(latencies) // 2] if latencies else None,
        "latency_p95_ms": latencies[int(len(latencies) * 0.95)] if latencies else None,
    }


@router.get("/decisions")
async def decisions(after: int = 0, limit: int = 100):
    """Baris log untuk Monitor. after=offset byte (polling murah); 0 = 100 baris terakhir."""
    try:
        raw = LOG_PATH.read_bytes()
    except OSError:
        return {"rows": [], "offset": 0}
    rows: list[tuple[int, dict]] = []
    pos = 0
    for line in raw.split(b"\n"):
        start, pos = pos, pos + len(line) + 1
        line = line.strip()
        if not line:
            continue
        try:
            rows.append((start, json.loads(line)))
        except ValueError:
            continue
    if after <= 0:
        rows = rows[-limit:]
    else:
        rows = [r for r in rows if r[0] >= after][:500]
    return {"rows": [r[1] for r in rows], "offset": len(raw)}


@router.get("/status")
async def status():
    light, heavy = tiers_cfg.current_models(LIGHT_MODEL, HEAVY_MODEL)
    rows = _read_rows()
    errors = sum(1 for r in rows if r.get("status", 0) >= 400)
    return {
        "ok": True,
        "light": light,
        "heavy": heavy,
        "tiers_source": "config/tiers.json" if tiers_cfg.load_tiers() else ".env",
        "log_rows": len(rows),
        "error_rows": errors,
        "last_ts": rows[-1].get("ts") if rows else None,
    }


@router.get("/tiers")
async def get_tiers():
    light, heavy = tiers_cfg.current_models(LIGHT_MODEL, HEAVY_MODEL)
    return {"light": light, "heavy": heavy,
            "source": "config/tiers.json" if tiers_cfg.load_tiers() else ".env"}


class TiersBody(BaseModel):
    light: str
    heavy: str


@router.put("/tiers")
async def put_tiers(body: TiersBody, request: Request):
    if not same_origin(request):
        raise HTTPException(403, "Origin tidak diizinkan")
    for name, value in (("light", body.light), ("heavy", body.heavy)):
        if not tiers_cfg.MODEL_RE.fullmatch(value):
            raise HTTPException(400, f"Nama model {name} tidak valid")
    tiers_cfg.save_tiers(body.light, body.heavy)
    return {"ok": True, "light": body.light, "heavy": body.heavy}
