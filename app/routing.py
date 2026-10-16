"""Logika routing murni (tanpa FastAPI) supaya mudah dites.

Ide: nilai "seberapa berat" pesan PENGGUNA terakhir dengan skor sederhana.
Skor >= threshold -> tier "heavy" (model kuat), selain itu "light" (model murah).

Catatan desain:
- Yang dinilai hanya pesan role "user", BUKAN hasil tool. Hasil tool pendek
  akan salah terbaca "ringan" padahal tugasnya berat.
- Keputusan dikunci (sticky) selama satu giliran pengguna. Agent mengirim ulang
  seluruh konteks di tiap langkah, dan cache prompt hanya berlaku per model,
  jadi ganti model di tengah giliran = konteks dihitung ulang penuh.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any

# Sinyal kuat: hampir pasti butuh penalaran lebih (+3)
STRONG_HEAVY = (
    "arsitektur", "architecture", "merancang", "rancang", "design a system",
    "security review", "review keamanan", "vulnerab", "celah keamanan",
    "root cause", "race condition", "memory leak", "migrasi database",
    "database migration", "threat model",
)
# Sinyal sedang (+2)
MEDIUM_HEAVY = (
    "debug", "troubleshoot", "stack trace", "traceback", "refactor",
    "optimasi", "optimize", "performance", "investigate", "analisis",
    "analyze", "kenapa", "mengapa", "tidak berfungsi", "gagal", "bug",
)
# Sinyal ringan (-1 per kata, maksimal -3)
LIGHT_HINTS = (
    "rename", "ganti nama", "format", "typo", "komentar", "comment",
    "jelaskan", "explain", "ringkas", "summarize", "terjemah", "translate",
    "boilerplate", "contoh", "sederhana", "simple", "tambahkan log",
)

STACK_RE = re.compile(
    r"traceback \(most recent call last\)"
    r"|\bat [\w.$<>]+ \(.*:\d+:\d+\)"
    r"|^\s+file \".*\", line \d+",
    re.IGNORECASE | re.MULTILINE,
)
PATH_RE = re.compile(
    r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|sql|go|rs|java|rb|php|css|html|json|ya?ml|toml)\b",
    re.IGNORECASE,
)
# Panggilan bantu otomatis (judul/ringkasan percakapan) -> selalu ringan
AUX_RE = re.compile(
    r"(generate|create|write).{0,40}\btitle\b|buat(kan)?\s+judul|short title"
    r"|summar(y|ize)\s+(of\s+)?(the\s+)?conversation",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class Decision:
    tier: str          # "light" atau "heavy"
    reason: str        # alasan singkat untuk log
    score: int
    est_tokens: int
    session: str       # hash pendek, bukan isi pesan
    cached: bool = False


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()[:16]


def content_to_text(content: Any) -> str:
    """Ambil teks dari content bertipe string atau daftar bagian (multimodal)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                parts.append(p["text"])
        return "\n".join(parts)
    return ""


def estimate_tokens(messages: list[dict]) -> int:
    """Perkiraan kasar: 1 token ~ 4 karakter. Cukup untuk heuristik, bukan penagihan."""
    chars = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        chars += len(content_to_text(m.get("content")))
        if m.get("tool_calls"):
            chars += len(json.dumps(m["tool_calls"], ensure_ascii=False))
    return chars // 4


class TurnCache:
    """Menyimpan tier per giliran pengguna (in-memory, dengan TTL)."""

    def __init__(self, ttl_seconds: int = 6 * 3600, max_items: int = 2000):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[str, tuple[str, str, float]] = {}

    def get(self, session: str, turn: str) -> str | None:
        item = self._data.get(session)
        if not item:
            return None
        tier, saved_turn, ts = item
        if time.time() - ts > self.ttl or saved_turn != turn:
            return None
        return tier

    def set(self, session: str, turn: str, tier: str) -> None:
        if len(self._data) >= self.max_items:
            oldest = min(self._data, key=lambda k: self._data[k][2])
            self._data.pop(oldest, None)
        self._data[session] = (tier, turn, time.time())


def decide(
    messages: list[dict],
    has_tools: bool,
    cache: TurnCache,
    threshold: int = 3,
) -> Decision:
    user_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
    first = content_to_text(user_msgs[0].get("content")) if user_msgs else ""
    last = content_to_text(user_msgs[-1].get("content")) if user_msgs else ""
    session = _h(first[:2000])
    turn = _h(f"{last}|{len(user_msgs)}")
    est = estimate_tokens(messages)

    # 1) Masih giliran pengguna yang sama (agent sedang looping) -> pakai tier yang sama
    cached = cache.get(session, turn)
    if cached:
        return Decision(cached, "sticky (giliran sama)", 0, est, session, True)

    # 2) Panggilan bantu otomatis tanpa tool -> ringan
    if not has_tools and AUX_RE.search(last):
        cache.set(session, turn, "light")
        return Decision("light", "panggilan bantu (judul/ringkasan)", 0, est, session)

    text = last.lower()
    score = 0
    reasons: list[str] = []

    strong = [k for k in STRONG_HEAVY if k in text]
    if strong:
        score += min(3 * len(strong), 6)
        reasons.append(f"kuat:{','.join(strong[:3])}")

    medium = [k for k in MEDIUM_HEAVY if k in text]
    if medium:
        score += min(2 * len(medium), 4)
        reasons.append(f"sedang:{','.join(medium[:3])}")

    if STACK_RE.search(last):
        score += 2
        reasons.append("stack-trace")

    paths = {p.lower() for p in PATH_RE.findall(last)}
    if len(paths) >= 3:
        score += 2
        reasons.append(f"banyak-file:{len(paths)}")

    if last.count("```") >= 4:  # >= 2 blok kode
        score += 1
        reasons.append("banyak-kode")

    if len(last) > 1500:
        score += 2
        reasons.append("pesan-panjang")
    elif len(last) > 600:
        score += 1
        reasons.append("pesan-agak-panjang")

    if est > 30_000:
        score += 2
        reasons.append("konteks>30k")
    elif est > 12_000:
        score += 1
        reasons.append("konteks>12k")

    light = [k for k in LIGHT_HINTS if k in text]
    if light:
        score -= min(len(light), 3)
        reasons.append(f"ringan:{','.join(light[:3])}")

    tier = "heavy" if score >= threshold else "light"
    cache.set(session, turn, tier)
    return Decision(tier, "; ".join(reasons) or "tanpa-sinyal", score, est, session)
