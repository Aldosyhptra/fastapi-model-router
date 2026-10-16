@echo off
rem Kontrol router kompleksitas (gateway agent: lokal / VPS).
rem Pakai: router.cmd [start|bg|stop|status]   (tanpa argumen = status)
rem   start  : foreground - Ctrl+C untuk berhenti
rem   bg     : jalan minimized di background
rem   status : tampilkan status lalu keluar
rem   stop   : matikan proses yang jalan di port ini
setlocal enabledelayedexpansion
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "PORT=8000"
set "HOST=127.0.0.1"
cd /d "%ROOT%"

rem Bind host/port dioverride lewat .env (BIND_HOST / BIND_PORT) - untuk VPS: BIND_HOST=0.0.0.0
for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%.env") do (
  if /i "%%a"=="BIND_PORT" set "PORT=%%b"
  if /i "%%a"=="BIND_HOST" set "HOST=%%b"
)
set "URL=http://127.0.0.1:%PORT%"

if /i "%~1"=="stop" goto :stop
if /i "%~1"=="bg" goto :bg
if /i "%~1"=="start" goto :start

:status
curl -s -m 3 -o nul "%URL%/health" 2>nul
if errorlevel 1 (
  echo Router   : OFF
  echo Nyalakan : router.cmd start    ^(foreground - Ctrl+C berhenti^)
  echo            router.cmd bg      ^(background minimized^)
  exit /b 1
)
goto :report

:start
if not exist "%PY%" (
  echo Venv belum ada: %PY%
  echo Jalankan: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
curl -s -m 3 -o nul "%URL%/health" 2>nul
if not errorlevel 1 (
  echo Router sudah ON - tidak memulai instance kedua.
  goto :report
)
echo Menyalakan router di %HOST%:%PORT% (foreground - Ctrl+C untuk berhenti)...
"%PY%" -m uvicorn app.main:app --host %HOST% --port %PORT%
echo Router berhenti.
exit /b 0
:bg
if not exist "%PY%" (
  echo Venv belum ada: %PY%
  echo Jalankan: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
curl -s -m 3 -o nul "%URL%/health" 2>nul
if not errorlevel 1 (
  echo Router sudah ON.
  exit /b 0
)
if not exist "%ROOT%logs" mkdir "%ROOT%logs"
start "Model Router" /min /d "%ROOT%" cmd /c ""%PY%" -m uvicorn app.main:app --host %HOST% --port %PORT% >> logs\uvicorn.log 2>&1"
echo Menyalakan router di %HOST%:%PORT% (background) ...
for /l %%i in (1,1,25) do (
  ping -n 2 127.0.0.1 >nul
  curl -s -m 3 -o nul "%URL%/health" 2>nul
  if not errorlevel 1 goto :report
)
echo Gagal menyalakan. Cek log: %ROOT%logs\uvicorn.log
exit /b 1

:report
echo Router        : ON
set "HEALTH=%TEMP%\router_health.json"
curl -s -m 3 -o "%HEALTH%" "%URL%/health" 2>nul
if not exist "%HEALTH%" (
  echo Gagal mengambil /health dari %URL% - router TIDAK merespons.
  exit /b 1
)
"%PY%" -c "import json,io;h=json.load(io.open(r'%HEALTH%',encoding='utf-8'));print('Base URL     : '+str(h.get('public_url','-')));print('Light model  : '+str(h.get('light','-')));print('Heavy model  : '+str(h.get('heavy','-')));print('Upstream key : '+('terisi' if h.get('configured') else 'BELUM DIISI (cek .env)'))"
set "N=0"
if exist "%ROOT%logs\decisions.jsonl" (
  "%PY%" -c "import io;print(sum(1 for _ in io.open(r'%ROOT%logs\decisions.jsonl',encoding='utf-8')))" > "%TEMP%\router_n.txt" 2>nul
  set /p N=<"%TEMP%\router_n.txt"
)
echo Keputusan     : !N! tercatat di logs\decisions.jsonl
echo Terakhir:
powershell -NoProfile -Command "if (Test-Path '%ROOT%logs\decisions.jsonl') { Get-Content '%ROOT%logs\decisions.jsonl' -Tail 3 | ForEach-Object { $d = $_ | ConvertFrom-Json; '  [{0}] {1,-5} -> {2}  (HTTP {3}{4})' -f ([DateTimeOffset]::FromUnixTimeSeconds($d.ts).LocalDateTime.ToString('dd MMM HH:mm')), $d.tier, $d.model, $d.status, $(if ($d.reason) { ', ' + $d.reason }) } }" 2>nul

if not defined FG exit /b 0
echo.
echo Menjalankan di foreground - log di bawah. Ctrl+C untuk berhenti.
"%PY%" -m uvicorn app.main:app --host %HOST% --port %PORT%
echo Router berhenti.
exit /b 0

:stop
set "FOUND="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr LISTENING ^| findstr ":%PORT%"') do (
  taskkill /f /pid %%p >nul 2>&1
  echo Router dimatikan - pid %%p
  set "FOUND=1"
)
if not defined FOUND echo Tidak ada router yang jalan di port %PORT%
exit /b 0
