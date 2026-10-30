# Model Router

Router model lokal yang memilih model upstream secara dinamis berdasarkan
berat tugas — ringan pakai flash, berat pakai pro. Dua keputusan: model apa
dan apakah thinking boleh.

## Cara kerja

Klien kirim request ke `http://127.0.0.1:8000/v1` dengan model `"auto"`.
Router skor dari kata kunci + sinyal kerja agen (arsitektur +3, debug +2,
loop panjang +1/2). Sinyal mutasi (+2) dan file sumber (+1) hanya dihitung
setelah loop >= 6 pesan tool, supaya satu edit tunggal tidak langsung memicu
heavy. Skor >= threshold -> heavy, else -> light. Threshold default 3
(`HEAVY_THRESHOLD`); benchmark agen di bawah memakai 4.
Tier hanya naik di tengah giliran (upgrade satu arah), tidak pernah turun,
supaya cache prompt per model tidak pecah.
Tidak ada biaya keputusan (sub-ms, tanpa classifier).

Kebijakan thinking: light -> effort rendah, heavy -> effort tinggi.

Keputusan tercatat di `logs/decisions.jsonl` per baris.

## Mulai

```bash
git clone https://github.com/Aldosyhptra/fastapi-model-router.git
cd fastapi-model-router
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

Salin `.env.example` ke `.env`, isi `OPENAI_API_KEY` dan `OPENAI_BASE_URL`.
Pilih model di `.env`: `LIGHT_MODEL` dan `HEAVY_MODEL`.

```bash
router.cmd start   # foreground (Ctrl+C berhenti)
router.cmd bg      # minimized background
router.cmd stop    # matikan
router.cmd status  # cek status
```

## Pilot HTTP awal (17 Okt 2026)

Pilot ini mengirim prompt langsung ke router (bukan lewat agen). Sudah digantikan oleh benchmark agen di bawah.

100 call, 20 prompt x 5 lane, sequential, `max_tokens=300`, `temperature=0`.
Model: light = `mimo-v2.6-flash`, heavy = `mimo-v2.6-pro`.

| Lane | P50 latency | Cost |
|---|---|---|
| pro-langsung | 9700ms | $0.0047 |
| flash-langsung | 11079ms | $0.0014 |
| **router-auto** | 11260ms | **$0.0034** |
| router-light | 8654ms | $0.0016 |
| router-heavy | 8651ms | $0.0049 |

`router-auto` **hemat 30% vs semua-heavy**, tier accuracy 100% (20/20).

## Benchmark agen (Hermes, 30 Okt 2026)

Mengukur router dari sisi agen sungguhan, bukan HTTP langsung: Hermes Agent
mengerjakan tugas coding pada proyek Next.js, lalu hasilnya dinilai secara
otomatis. Yang diukur: tingkat lolos, biaya, waktu, dan perilaku routing.

### Lane

| Lane | Model yang dikirim ke router | Arti |
|---|---|---|
| pro-langsung | `mimo-v2.6-pro` | Selalu model kuat |
| flash-langsung | `mimo-v2.6-flash` | Selalu model murah |
| router-auto | `auto` | Router memilih light/heavy |
| router-light | `light` | Dipaksa tier light |
| router-heavy | `heavy` | Dipaksa tier heavy |

Semua lane lewat router (model eksplisit = passthrough tanpa penilaian),
sehingga pencatatan usage seragam di `logs/decisions.jsonl`.

### Tata cara

1. **Fixture**: proyek `create-next-app` (TypeScript, Tailwind, App Router) di
   folder terpisah di luar router (`D:ench
ext-fixture`), berisi kode contoh
   dengan bug yang sengaja ditanam. Tag `bench-base` adalah kondisi awal.
2. **Setiap run** dimulai dari `git reset --hard bench-base` dan hapus `.next`,
   jadi kondisi awal identik.
3. **Prompt** dikirim ke Hermes (`hermes chat -q ... --provider model-router`)
   dengan `[bench-run:<id>]` di depan supaya cache keputusan router tidak
   terbawa antar run. Prompt satu baris (newline terpotong di shim `.CMD`
   Windows dan membuat agen menjawab "tidak ada tugas").
4. **Agen dikunci ke fixture** lewat `terminal.cwd` di profil Hermes `bench`
   (profil terpisah, tanpa memori atau skill pribadi).
5. **Penilaian** dilakukan harness, bukan agen: `tsc`, `build`, cek pola kode
   (`file_contains` / `file_not_contains`), dan smoke HTTP. Perubahan diambil
   dari git diff sebelum penilaian.
6. Urutan lane diacak per (tugas, ulangan) dengan seed tetap.

### Kriteria

- **Lolos (PASS)**: semua check pada tugas itu benar. Lolos berarti tugas
  terpenuhi menurut check otomatis, bukan penilaian kualitas desain.
- **FAIL**: ada check yang gagal (diff kosong, pola tidak ada, atau build gagal).
- **Infra error**: tidak ada panggilan tercatat di router (gateway putus).
  Dikeluarkan dari tingkat lolos dan dilaporkan terpisah. Tidak ada run
  seperti ini di hasil akhir.
- **Biaya**: dihitung dari `usage` di log router dengan tabel harga per juta
  token (flash: input $0.14, cache $0.003, output $0.28; pro: input $0.435,
  cache $0.004, output $0.87).
- Label light/heavy per tugas adalah dugaan awal, bukan hasil validasi.

### Konfigurasi

- Dataset: 12 tugas (6 light `L01`–`L06`, 6 heavy `H01`–`H06`).
- Ulangan: 3 per tugas per lane, 180 run total.
- `HEAVY_THRESHOLD=4`, `max_turns=25`, timeout 1800 detik per run.
- Kebijakan eskalasi: mutasi file sumber hanya dihitung setelah loop >= 6 pesan
  tool (lihat Cara kerja). Ini diubah sebelum run penuh karena kalibrasi
  menunjukkan satu edit tunggal sudah memicu heavy dan membuat biaya auto
  melonjak.

### Hasil (180 run, 0 infra error, 0 timeout)

| Lane | Lolos | Biaya/run | Waktu/run | Panggilan/run | Light / Heavy (panggilan) |
|---|---|---|---|---|---|
| pro-langsung | 86% | $0.0103 | 206 s | 12.2 | – |
| flash-langsung | 81% | $0.0039 | 217 s | 13.0 | – |
| **router-auto** | 83% | **$0.0087** | 174 s | 12.2 | 154 / 285 |
| router-light | 86% | $0.0031 | 199 s | 12.2 | 440 / 0 |
| router-heavy | 89% | $0.0104 | 214 s | 12.1 | 0 / 434 |

Per jenis tugas (lolos / biaya per run):

| Lane | Light: lolos | Light: biaya | Heavy: lolos | Heavy: biaya |
|---|---|---|---|---|
| pro-langsung | 100% | $0.0035 | 72% | $0.0171 |
| flash-langsung | 100% | $0.0017 | 61% | $0.0061 |
| router-auto | 100% | $0.0042 | 67% | $0.0132 |
| router-light | 100% | $0.0014 | 72% | $0.0049 |
| router-heavy | 100% | $0.0048 | 78% | $0.0160 |

Penghematan berpasangan (tugas dan ulangan yang sama): router-auto **16%**
lebih murah dari pro-langsung dan **17%** lebih murah dari router-heavy.

### Pembacaan

- **Router-auto lebih murah dari pro-langsung** (sekitar 16%) dengan tingkat
  lolos yang hampir sama (83% vs 86%). Selisih 3 poin masih dalam noise untuk
  36 run per lane, jadi "kualitasnya setara" belum terbukti secara statistik.
- **Penghematan belum besar** karena router-auto memakai heavy untuk sekitar
  65% panggilan (285 dari 439). Heavy di tugas heavy memang sering dibutuhkan,
  tapi eskalasi di tugas light juga masih terjadi.
- **Router-light dan flash lebih murah**, dan di dataset ini tingkat lolos
  tugas light-nya sama dengan pro (100%). Artinya tugas light di dataset ini
  memang ringan.
- **Tugas heavy tidak membedakan lane dengan tegas.** Pro (72%) dan router-light
  (72%) hampir sama, dan router-heavy 78%. Ini tanda label heavy belum tentu
  tepat, atau check-nya terlalu longgar.
- **H06 gagal di semua lane (0/3 setiap lane).** Ini kemungkinan tugas atau
  check yang bermasalah, bukan kelemahan satu lane. Perlu diperiksa sebelum
  dataset dipakai untuk klaim yang lebih kuat.

### Batasan

- Penilaian statis: build, tsc, dan pola kode. Tidak menilai kualitas desain
  atau perilaku UI di browser (AGENTS.md melarang menjalankan dev server).
- Dataset kecil (12 tugas) dan label belum divalidasi. Kesimpulan hanya berlaku
  untuk jenis tugas ini.
- Threshold dan kebijakan eskalasi dipilih dengan melihat hasil kalibrasi
  pada tugas yang sama (L01, H01), jadi hasil ini bisa bias ke dataset itu.
  Untuk klaim yang kuat, pisahkan tugas dev dan test.
- Kalibrasi awal (sebelum isolasi fixture, dan saat prompt masih rusak) dibuang
  dan tidak dihitung.

## Tech stack

Python 3 + FastAPI + uvicorn + httpx + python-dotenv + pytest.