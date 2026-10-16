"""Router model lokal: meniru API OpenAI, memilih model OpenAI-compatible berdasarkan beratnya tugas.

Jalankan:  uvicorn app.main:app --host 127.0.0.1 --port 8000
Di Hermes: custom endpoint  http://127.0.0.1:8000/v1 , model "auto"
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from .routing import TurnCache, decide

try:  # .env opsional
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

log = logging.getLogger("openai-router")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Provider apa pun yang API-nya kompatibel OpenAI (OpenAI, OpenRouter, reseller, server lokal).
BASE_URL = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
LIGHT_MODEL = os.environ.get("LIGHT_MODEL", "deepseek-v4-flash")
HEAVY_MODEL = os.environ.get("HEAVY_MODEL", "deepseek-v4-pro")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY", "")
HEAVY_THRESHOLD = int(os.environ.get("HEAVY_THRESHOLD", "3"))
LOG_PATH = Path(os.environ.get("LOG_PATH", "logs/decisions.jsonl"))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
BIND_PORT = os.environ.get("BIND_PORT", "8000")
MAX_BODY_BYTES = 20 * 1024 * 1024
# Kebijakan thinking: light = jangan buang token reasoning (param dibuang sebelum forward);
# heavy = boleh thinking. HEAVY_REASONING_EFFORT (mis. "high") mengisi reasoning_effort
# saat klien tidak mengirim apa pun - kosongkan kalau model upstream menolak param ini.
THINKING_KEYS = ("reasoning_effort", "reasoning", "thinking", "enable_thinking", "extended_thinking")
HEAVY_REASONING_EFFORT = os.environ.get("HEAVY_REASONING_EFFORT", "").strip()


def apply_thinking_policy(tier: str, payload: dict) -> str:
    """Atur param thinking sesuai tier. Return tag untuk log ("" kalau tidak ada perubahan)."""
    if tier == "light":
        stripped = [k for k in THINKING_KEYS if k in payload]
        for k in stripped:
            payload.pop(k, None)
        return "thinking:strip" if stripped else ""
    if tier == "heavy" and HEAVY_REASONING_EFFORT:
        if not any(k in payload for k in THINKING_KEYS):
            payload["reasoning_effort"] = HEAVY_REASONING_EFFORT
            return f"thinking:{HEAVY_REASONING_EFFORT}"
    return ""

# Nama model virtual yang diterima dari klien (Hermes)
AUTO_ALIASES = {"auto", "router", "smart"}

cache = TurnCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not BASE_URL or not API_KEY:
        log.warning("OPENAI_BASE_URL / OPENAI_API_KEY belum diisi. Cek file .env")
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10)
    )
    yield
    await app.state.client.aclose()


app = FastAPI(title="OpenAI-compatible Complexity Router", lifespan=lifespan)


def check_local_auth(request: Request) -> None:
    """Opsional: lindungi router dari proses lain di komputer yang sama."""
    if not LOCAL_API_KEY:
        return
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(token, LOCAL_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


def write_log(entry: dict) -> None:
    """Catat keputusan routing. TIDAK menyimpan isi prompt atau API key."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:  # log gagal tidak boleh mematikan request
        log.warning("gagal menulis log: %s", e)


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": {"message": message, "type": "router_error"}}, status_code=status)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "public_url": PUBLIC_BASE_URL or f"http://127.0.0.1:{BIND_PORT}/v1",
        "light": LIGHT_MODEL,
        "heavy": HEAVY_MODEL,
        "configured": bool(BASE_URL and API_KEY),
    }


@app.get("/v1/models")
async def list_models(request: Request):
    check_local_auth(request)
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": mid, "object": "model", "created": now, "owned_by": "local-router"}
            for mid in ("auto", "light", "heavy")
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    check_local_auth(request)

    if not BASE_URL or not API_KEY:
        return error(500, "Router belum dikonfigurasi (OPENAI_BASE_URL / OPENAI_API_KEY).")

    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return error(413, "Request terlalu besar.")

    try:
        payload = await request.json()
    except Exception:
        return error(400, "Body bukan JSON yang valid.")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return error(400, "Field 'messages' wajib berupa daftar yang tidak kosong.")

    # Tentukan model
    requested = str(payload.get("model", "auto"))
    if requested in AUTO_ALIASES:
        d = decide(messages, bool(payload.get("tools")), cache, HEAVY_THRESHOLD)
        tier, reason, score = d.tier, d.reason, d.score
        model = HEAVY_MODEL if tier == "heavy" else LIGHT_MODEL
        session, est = d.session, d.est_tokens
    elif requested == "light":
        tier, reason, score, model, session, est = "light", "dipaksa klien", 0, LIGHT_MODEL, "-", 0
    elif requested == "heavy":
        tier, reason, score, model, session, est = "heavy", "dipaksa klien", 0, HEAVY_MODEL, "-", 0
    else:  # nama model lain: teruskan apa adanya
        tier, reason, score, model, session, est = "passthrough", "model eksplisit", 0, requested, "-", 0

    upstream_payload = dict(payload)
    upstream_payload["model"] = model
    t_tag = apply_thinking_policy(tier, upstream_payload)
    if t_tag:
        reason = f"{reason}; {t_tag}" if reason else t_tag
    stream = bool(payload.get("stream"))
    url = f"{BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    client: httpx.AsyncClient = request.app.state.client
    started = time.time()
    extra_headers = {"X-Router-Tier": tier, "X-Router-Model": model}

    def log_entry(status: int, usage: dict | None) -> None:
        write_log({
            "ts": int(started), "session": session, "tier": tier, "model": model,
            "reason": reason, "score": score, "est_tokens": est, "stream": stream,
            "status": status, "latency_ms": int((time.time() - started) * 1000),
            "usage": usage,
        })

    try:
        if not stream:
            resp = await client.post(url, json=upstream_payload, headers=headers)
            usage = None
            try:
                usage = resp.json().get("usage")
            except Exception:
                pass
            log_entry(resp.status_code, usage)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
                headers=extra_headers,
            )

        # Streaming (SSE): buka koneksi dulu supaya status error bisa diteruskan apa adanya
        upstream_req = client.build_request("POST", url, json=upstream_payload, headers=headers)
        resp = await client.send(upstream_req, stream=True)
        if resp.status_code >= 400:
            body = await resp.aread()
            await resp.aclose()
            log_entry(resp.status_code, None)
            return Response(
                content=body,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
                headers=extra_headers,
            )

        async def relay():
            usage = None
            buf = ""
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    # Intip baris SSE untuk mengambil data usage (jika dikirim provider)
                    buf += chunk.decode("utf-8", "ignore")
                    *lines, buf = buf.split("\n")
                    for line in lines:
                        if line.startswith("data:") and '"usage"' in line:
                            try:
                                u = json.loads(line[5:].strip()).get("usage")
                                if u:
                                    usage = u
                            except Exception:
                                pass
            finally:
                await resp.aclose()
                log_entry(resp.status_code, usage)

        return StreamingResponse(
            relay(),
            media_type="text/event-stream",
            headers={**extra_headers, "Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except httpx.TimeoutException:
        log_entry(504, None)
        return error(504, "Upstream timeout.")
    except httpx.HTTPError as e:
        log_entry(502, None)
        log.warning("upstream error: %s", type(e).__name__)
        return error(502, "Tidak bisa menghubungi upstream.")
