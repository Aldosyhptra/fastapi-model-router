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

## Tech stack

- **Python 3** + **FastAPI** + **uvicorn** (server), **httpx** (client async ke upstream)
- **python-dotenv** untuk konfigurasi `.env`
- **pytest** untuk unit test
- Log keputusan: `logs/decisions.jsonl` (append-only, JSON per baris) — dipakai untuk audit penghematan dan menemukan tugas yang salah rute.
- Tanpa database, tanpa dependensi berat: ~430 baris kode inti (`app/main.py` + `app/routing.py`).

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
| Kata kunci kuat (arsitektur, security review, root cause, desain, refactor, ...) | +3 per kata (maks 6) |
| Kata kunci sedang (debug, optim*, performance, analisis, ...) | +2 per kata (maks 4) |
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

## Benchmark (17 Okt 2026)

Pengukuran efisiensi router: **prompt & parameter sama persis**, yang dibedakan hanya
jalur (langsung vs router) dan model (flash vs pro).

### Spesifikasi

| | |
|---|---|
| Tanggal | 17 Oktober 2026 |
| Prompt | 20 (10 ringan + 10 berat), label tier ditulis manual |
| Parameter | `max_tokens=300`, `temperature=0`, `stream=true` + `stream_options.include_usage` |
| Call | 100 sequential (20 prompt x 5 lane), tanpa konkurensi |
| Sistem | Windows 11, satu mesin, koneksi lokal ke upstream (tanpa proxy lain) |
| Metode | HTTP langsung via Python stdlib (`urllib`) ke endpoint `/v1/chat/completions` — lane langsung memakai upstream, lane router memakai router lokal |
| Upstream | SumoPod (OpenAI-compatible) |
| Model | light = `mimo-v2.6-flash`, heavy = `mimo-v2.6-pro` |
| Penggunaan riil | 265 request dari sesi Hermes Agent v0.21.5 (Windows 11, client agent dengan terminal/file tools & skill coding) |

### Hasil

| Lane | OK | Avg latency | P50 latency | Tok in/out | Cost total |
|---|---|---|---|---|---|
| pro-langsung | 20 | 9744ms | 9700ms | 860/5017 | $0.0047 |
| flash-langsung | 20 | 12509ms | 11079ms | 860/4480 | $0.0014 |
| router-auto | 20 | 15557ms | 11260ms | 860/5003 | $0.0034 |
| router-light | 20 | 9047ms | 8654ms | 860/5169 | $0.0016 |
| router-heavy | 20 | 8938ms | 8651ms | 860/5145 | $0.0049 |

- **Auto vs semua-heavy (router-heavy): hemat 30%** ($0.0034 vs $0.0049) dengan tier
  accuracy 100% — biaya routing hanya dibayar untuk tugas yang benar-benar berat.
- **router-heavy vs pro-langsung**: `reasoning_effort=high` di-inject kebijakan thinking
  untuk tugas berat — itu memang biaya yang dibeli secara sadar, bukan kebocoran.
- Panjang output bervariasi antar-run meski `temperature=0` (perbedaan backend upstream);
  karenanya angka token/output dibaca sebagai biaya relatif, bukan perbandingan mutlak.
- Overhead router sendiri tidak terlihat di latency (keputusan skor sub-milidetik);
  selisih latency antar lane lebih banyak dipengaruhi antrian upstream.

### Tier accuracy (auto vs label): 100% (20/20)

Sebelumnya 80% (16/20) dengan 4 miss semuanya tugas berat yang salah dianggap ringan
(false-light): 2 kasus mepet threshold (score 2), 2 kasus kalah morfologi bahasa Indonesia
(`mengoptimalkan` tidak mengandung `optimasi`, `desain` belum masuk kamus). Perbaikan:
kata kunci kuat ditambah (`desain`, `refactor` dipromosikan ke sinyal kuat) dan kata kunci
sedang dibuat berbasis prefiks (`optim`) sehingga turunan imbuhan ikut terdeteksi.
Setelah perbaikan: 20/20, tanpa mengorbankan prompt ringan.

## Keterbatasan

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
