"""Logika routing murni (tanpa FastAPI) supaya mudah dites.

Ide: nilai "seberapa berat" pesan PENGGUNA terakhir dengan skor sederhana.
Skor >= threshold -> tier "heavy" (model kuat), selain itu "light" (model murah).

Catatan desain:
- Yang dinilai teks pesan role "user" TERAKHIR + sinyal kerja agen (tool_calls mutasi
  dan panjang loop) pada pesan setelah user terakhir.
- Keputusan per giliran dikunci, tapi boleh UPGRADE light->heavy di tengah giliran saat
  sinyal kerja agen naik (satu arah; downgrade merusak prompt-cache). Agent mengirim ulang
  seluruh konteks di tiap langkah, dan cache prompt hanya berlaku per model.
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
    "desain",      # "desain strategi/sistem ..." - kata kerja sering terlewat
    "refactor",    # jarang ringan; dipindah dari medium agar tidak mepet threshold
)
# Sinyal sedang (+2) - "optim" sengaja prefiks: kena optimasi/optimalkan/mengoptimasi/optimization
MEDIUM_HEAVY = (
    "debug", "troubleshoot", "stack trace", "traceback",
    "optim", "performance", "investigate", "analisis",
    "analyze", "kenapa", "mengapa", "tidak berfungsi", "gagal", "bug",
    "lambat", "hit rate",
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
# Tool yang MUTASI (agent mengubah sesuatu) -> sinyal kerja berat
MUTATION_RE = re.compile(
    r"write|edit|patch|apply|delete|remove|rename|move|copy|insert|update"
    r"|commit|push|install|migrat",
    re.IGNORECASE,
)
# Tool shell/terminal: mutasi dilihat dari isi command-nya
SHELL_RE = re.compile(r"^(terminal|bash|shell|run|exec|command)", re.IGNORECASE)
# File sumber kode (bukan dokumen/config) -> risiko layout/bug, perlu model kuat
SRC_EXT_RE = re.compile(r"\.(?:py|ts|tsx|js|jsx|html|css|scss|sql|go|rs|java|rb|php)\b", re.IGNORECASE)


def agent_score(messages: list[dict]) -> tuple[int, list[str]]:
    """Nilai APA YANG SEDANG DILAKUKAN agen pada giliran ini.

    Sinyal diambil dari pesan setelah user terakhir (tool_calls & step agent),
    bukan dari teks user. Dipakai untuk meng-upgrade tier di tengah giliran.
    """
    last_user = -1
    for i, m in enumerate(messages):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = i
    tail = [m for m in messages[last_user + 1:] if isinstance(m, dict)]
    score = 0
    reasons: list[str] = []

    mutated = False
    src_edit = False
    for m in tail:
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function", tc) if isinstance(tc, dict) else {}
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name", ""))
            args = str(fn.get("arguments", ""))
            if MUTATION_RE.search(name) or (SHELL_RE.search(name) and MUTATION_RE.search(args)):
                mutated = True
                if SRC_EXT_RE.search(args):
                    src_edit = True
    n = len(tail)
    # Mutasi file sumber hanya dihitung setelah loop >= 6 pesan tool; satu edit
    # tunggal tidak memicu heavy (hemat biaya). Ceiling: belum ada sinyal
    # kegagalan check di router; upgrade path = baca hasil check dari klien.
    if mutated and n >= 6:
        score += 2
        reasons.append("mutasi")
    if src_edit and n >= 6:
        score += 1
        reasons.append("file-sumber")
    if n >= 12:
        score += 2
        reasons.append(f"loop-panjang:{n}")
    elif n >= 6:
        score += 1
        reasons.append(f"loop:{n}")
    return score, reasons


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


def base_score(last: str, est: int) -> tuple[int, list[str]]:
    """Skor dari teks pesan user terakhir + ukuran konteks."""
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

    return score, reasons


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

    # 1) Giliran sama: nilai ulang sinyal kerja agen; tier boleh NAIK saja
    #    (upgrade satu arah) - tidak pernah turun supaya cache prompt aman.
    #    total = skor-dasar + sinyal-agen-kini (tidak diakumulasi antar call,
    #    supaya satu mutasi tidak dihitung berkali-kali).
    prev = cache.get(session, turn)
    if prev is not None:
        prev_tier, base, base_reasons = prev
        a_score, a_reasons = agent_score(messages)
        total = base + a_score
        reasons = list(base_reasons) + a_reasons
        tier = "heavy" if total >= threshold else prev_tier
        if tier != prev_tier:
            reasons.append(f"upgrade:{prev_tier}->{tier}")
        cache.set(session, turn, (tier, base, base_reasons))
        return Decision(tier, "; ".join(reasons) or "sticky", total, est, session,
                        cached=(tier == prev_tier))

    # 2) Panggilan bantu otomatis tanpa tool -> ringan
    if not has_tools and AUX_RE.search(last):
        cache.set(session, turn, ("light", 0, ["panggilan-bantu"]))
        return Decision("light", "panggilan bantu (judul/ringkasan)", 0, est, session)

    # 3) Giliran baru: skor dasar dari teks user + sinyal kerja agen pada call pertama
    score, reasons = base_score(last, est)
    a_score, a_reasons = agent_score(messages)
    score += a_score
    reasons += a_reasons

    tier = "heavy" if score >= threshold else "light"
    cache.set(session, turn, (tier, score, reasons))
    return Decision(tier, "; ".join(reasons) or "tanpa-sinyal", score, est, session)
