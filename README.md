# OpenAI Complexity Router

Proxy lokal (FastAPI) yang meniru API OpenAI. Klien (Hermes dsb.) mengira ini provider biasa,
sementara di belakangnya router menilai beratnya tugas lalu memilih model dari **upstream mana pun
yang API-nya kompatibel OpenAI** — OpenAI resmi, OpenRouter, Azure, reseller, atau server lokal
(LM Studio / Ollama / vLLM):

```
Klien -> http://127.0.0.1:8000/v1 -> [nilai tugas] -> OpenAI-compatible upstream
                                         |- ringan -> LIGHT_MODEL
                                         `- berat  -> HEAVY_MODEL
```

Berjalan **hanya di komputermu** (bind ke `127.0.0.1`), tidak perlu hosting.

## Menjalankan (cepat)

Semua lewat cmd, dari folder proyek:

```bat
router.cmd start      :: nyalakan FOREGROUND di window ini (Ctrl+C berhenti) + status saat sudah ON
router.cmd bg         :: nyalakan MINIMIZED di background, log ke logs/uvicorn.log
router.cmd            :: status: ON/OFF, Base URL, model light/heavy, jumlah keputusan, 3 terakhir
router.cmd stop       :: matikan
```

`start` vs `bg`: dua-duanya nyalakan uvicorn; `bg` keluar sendiri setelah server hidup (window minimized),
`start` menahan window karena uvicorn berjalan di situ.

Contoh output `router.cmd` saat ON:

```
Router        : ON
Base URL     : http://127.0.0.1:8000/v1
Light model  : qwen3.8-flash
Heavy model  : glm-5.3-flash
Upstream key : terisi
Keputusan     : 169 tercatat di logs/decisions.jsonl
Terakhir:
  [15 Oct 14:36] heavy -> glm-5.3-flash  (HTTP 200, dipaksa klien)
```

Router mati = Hermes tidak bisa memanggil provider `model-router`. Untuk auto-recovery,
pasang watchdog (opsional, rekomendasi):

**Watchdog via Task Scheduler (self-healing, tanpa flash window)**

- Task `Hermes Model Router Watchdog` mengecek router tiap 5 menit. Router hidup -> tidak
  melakukan apa pun. Router mati -> menyalakan ulang minimized (`router.cmd bg`) dalam <5 menit.
- Action task: `wscript.exe "<folder proyek>\router-watchdog.vbs"` — file `.vbs` 2 baris itu
  menjalankan `router.cmd bg` dengan window style `0` (tersembunyi). Jangan pakai argumen
  `start` pada task: itu mode foreground, memunculkan window cmd tiap trigger (terlihat seperti
  proses mencurigakan) dan rawan ke-close manual.
- Bikin task sekali (sesuaikan `<path-proyek>` dengan lokasi folder ini di mesinmu):
  ```bat
  schtasks /create /tn "Hermes Model Router Watchdog" /sc minute /mo 5 ^
    /tr "wscript.exe \"<path-proyek>\router-watchdog.vbs\""
  ```
  Edit juga baris dalam `router-watchdog.vbs` agar menunjuk ke path proyekmu.
- Cek: `schtasks /query /tn "Hermes Model Router Watchdog" /fo LIST` — kolom "Task To Run"
  harus `wscript.exe ...vbs`, bukan `router.cmd` langsung. Hapus: `schtasks /delete /tn ... /f`.

## Deploy ke VPS (opsional)

Repo ini portable. Di `.env` VPS:

```
BIND_HOST=0.0.0.0            # WAJIB bersama LOCAL_API_KEY terisi + HTTPS via reverse proxy
PUBLIC_BASE_URL=https://domainmu.com/v1   # yang ditampilkan `router.cmd` dan dipakai client
```

Tanpa `PUBLIC_BASE_URL`, status otomatis menampilkan `http://127.0.0.1:<BIND_PORT>/v1`.
Kalau dibuka ke publik: satu-satunya pengaman adalah `LOCAL_API_KEY` (Bearer) — jangan
pernah expose tanpa itu, dan pakai HTTPS (Caddy/Nginx) karena key = saldo billing upstreammu.

## Menjalankan (manual)

```bash
# 1. Buat virtual environment
python -m venv .venv

# Windows (PowerShell):  .venv/Scripts/Activate.ps1
# Linux / macOS:         source .venv/bin/activate

# 2. Pasang dependency
pip install -r requirements.txt

# 3. Konfigurasi
cp .env.example .env        # Windows: copy .env.example .env
# lalu isi OPENAI_BASE_URL, OPENAI_API_KEY, LIGHT_MODEL, HEAVY_MODEL

# 4. Jalankan (jangan ganti host ke 0.0.0.0)
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Cek: buka http://127.0.0.1:8000/health dan http://127.0.0.1:8000/docs

## Tes cepat

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LOCAL_API_KEY" \
  -d '{"model":"auto","messages":[{"role":"user","content":"ganti nama variabel x jadi total"}]}' -i
```

Lihat header `X-Router-Tier` dan `X-Router-Model` di respons untuk mengetahui model yang dipilih.

## Pasang di Hermes

Router ini didaftarkan sebagai **provider OpenAI-compatible biasa** (tanpa plugin tambahan):

```bash
hermes config set providers.model-router.base_url "http://127.0.0.1:8000/v1"
hermes config set providers.model-router.key_env  "MODEL_ROUTER_API_KEY"
hermes config set providers.model-router.model    "auto"
hermes config set providers.model-router.models   '["auto","light","heavy"]'
```

`MODEL_ROUTER_API_KEY` di `~/.hermes/.env` harus sama dengan `LOCAL_API_KEY` di `.env` proyek ini
(Hermes membaca `.env` saat start, jadi restart sesi setelah mengubahnya).

Pakai sebagai model: `hermes -m auto --provider model-router`, atau `/model` di sesi berjalan.
Model `light` / `heavy` memaksa tier tanpa menilai tugas.

Catatan: kalau agent/klien kamu punya mekanisme router bawaan (mis. plugin router di Hermes),
nonaktifkan atau set semua perannya ke `auto` supaya tidak terjadi routing ganda — router ini
harus satu-satunya yang memutuskan.

## Cara menilai tugas (app/routing.py)

Skor dari pesan **user** terakhir (bukan hasil tool) + **sinyal kerja agen** per API call:

| Sinyal | Skor |
|---|---|
| Kata kunci kuat (arsitektur, security review, root cause, ...) | +3 per kata (maks 6) |
| Kata kunci sedang (debug, refactor, traceback, ...) | +2 per kata (maks 4) |
| Stack trace | +2 |
| 3+ nama file berbeda | +2 |
| 2+ blok kode fenced | +1 |
| Pesan panjang (>600 / >1500 karakter) | +1 / +2 |
| Konteks besar (>12k / >30k token) | +1 / +2 |
| Kata ringan (rename, format, jelaskan, ...) | -1 per kata (maks -3) |
| **Agen memanggil tool mutasi** (write/edit/patch/install/git commit, atau shell dengan perintah ubah) | **+2** |
| **Mutasi menyasar file sumber** (.py/.tsx/.js/.css/... bukan dokumen) | **+1** |
| **Loop agen panjang** (≥6 / ≥12 pesan setelah user terakhir) | **+1 / +2** |

Skor >= `HEAVY_THRESHOLD` (bawaan 3) -> heavy. Panggilan bantu otomatis (judul/ringkasan,
tanpa tool) selalu light.

**Kebijakan upgrade satu arah (versi 2):** keputusan awal di-cache per giliran pengguna
(in-memory, TTL 6 jam, maks 2000 sesi), tapi setiap API call sinyal kerja agen dinilai ulang.
Tier boleh **naik** light->heavy di tengah giliran (mis. user cuma minta "ubah warna" tapi agen
malah mengedit file sumber) — dan tidak pernah turun, supaya cache prompt upstream tidak
bolak-balik. Sinyal agen tidak diakumulasi antar call (mutasi yang sama tidak dihitung dua kali).

## Kebijakan thinking (reasoning)

- Tier **light**: param thinking (`reasoning_effort`, `thinking`, `enable_thinking`, dst.)
  otomatis **dibuang** sebelum forward — token reasoning di request ringan hanya memboroskan.
- Tier **heavy**: klien boleh thinking; kalau klien tidak mengirim apa pun, router mengisi
  `reasoning_effort` dari `HEAVY_REASONING_EFFORT` (mis. `high`). Kosongkan nilai ini kalau
  model upstream menolak param tersebut.
- Hasilnya tercatat di `decisions.jsonl`: `thinking:strip` (dibuang) atau `thinking:high` (diisi).

## Log

`logs/decisions.jsonl` berisi tier, model, alasan, skor, perkiraan token, latensi, dan
usage (jika provider mengirim). **Isi prompt dan API key tidak dicatat.**
Gunakan log ini untuk menghitung penghematan dan menemukan tugas yang salah dirutekan.

## Tes

```bash
.venv/Scripts/python.exe -m pytest tests -q
```
## Keterbatasan (jujur)

- Heuristik berbasis aturan: bisa salah menilai. Cek log dan sesuaikan kata kunci/threshold.
- Tidak bisa downgrade heavy->light dalam satu giliran (by design: lindungi prompt-cache).
- Upgrade light->heavy di tengah giliran tetap memakai cache (prompt yang dikirim identik;
  yang berubah hanya tujuan model).
- Estimasi token kasar (karakter / 4), bukan tokenizer asli.
- Cache keputusan ada di memori; hilang saat server restart.
- Belum ada eskalasi otomatis berbasis hasil (light gagal -> ulang di heavy).
- Streaming dan tool calling sudah diuji end-to-end lewat Hermes (2026-10-15), termasuk
  saat provider mengembalikan 429 di tengah jalan (diteruskan apa adanya, klien retry sendiri).
- Tidak ada rate limit atau batas biaya; pantau saldo billing upstreammu.

## Keamanan

- Jangan commit `.env` (sudah ada di `.gitignore`).
- Biarkan bind ke `127.0.0.1`. Isi `LOCAL_API_KEY` agar proses lain di komputer tidak bisa memakai kuncimu.
- Jangan kirim data sensitif ke model tanpa memahami kebijakan data provider.
