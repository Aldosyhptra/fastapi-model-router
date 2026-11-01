import { useEffect, useState } from "react";
import Sidebar from "../components/sidebar.jsx";
import StatCard from "../components/statcard.jsx";
import RequestLog from "../components/requestlog.jsx";
import Banner from "../components/banner.jsx";
import { fetchSummary, fetchDecisions, fetchStatus } from "../lib/api.jsx";
import { formatRibuan, formatDollar, formatDolarKeRupiah, formatPersen, formatMs, formatJam } from "../lib/format";

// Ringkasan: status router, filter waktu, 4 kartu angka, porsi tier, log 6 baris (F2, F5).
export default function Ringkasan({ halaman, setHalaman, onLogout }) {
  const [jendela, setJendela] = useState("24h");
  const [ringkas, setRingkas] = useState(null);
  const [status, setStatus] = useState(null);
  const [log, setLog] = useState([]);
  const [galat, setGalat] = useState(false);

  useEffect(() => {
    let hidup = true;
    Promise.all([fetchSummary(jendela), fetchStatus(), fetchDecisions(0, 6)]).then(([s, st, d]) => {
      if (!hidup) return;
      setRingkas(s);
      setStatus(st);
      setLog(d.rows);
      setGalat(!s);
    });
    return () => {
      hidup = false;
    };
  }, [jendela]);

  const r = ringkas;
  const totalTier = r ? (r.per_tier.light || 0) + (r.per_tier.heavy || 0) || 1 : 1;
  const porsiHeavy = r ? (r.per_tier.heavy || 0) / totalTier : null;

  return (
    <div className="flex">
      <Sidebar halaman={halaman} setHalaman={setHalaman} onLogout={onLogout} />
      <div className="flex-1 p-6 space-y-6 max-w-[1280px]">
        {galat && <Banner jenis="error">Data terbaru gagal dimuat — angka di bawah bisa sudah usang.</Banner>}

        {/* Status router */}
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Ringkasan</h1>
          <span className={`px-2 h-6 leading-6 rounded text-xs font-medium ${status?.ok ? "bg-ok/15 text-ok" : "bg-error/15 text-error"}`}>
            {status?.ok ? "ON" : "OFF"}
          </span>
          {status && (
            <span className="text-[13px] text-muted">
              {status.light} / {status.heavy} · sumber: {status.tiers_source}
              {status.last_ts && <> · log terakhir {formatJam(status.last_ts)}</>}
            </span>
          )}
          <div className="ml-auto flex gap-1">
            {[["1h", "1 jam"], ["24h", "24 jam"], ["all", "Semua"]].map(([id, label]) => (
              <button
                key={id}
                onClick={() => setJendela(id)}
                className={`h-8 px-3 rounded-md text-[13px] cursor-pointer ${
                  jendela === id ? "bg-primary/15 text-primary font-medium" : "text-muted hover:bg-surface-2"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* 4 kartu angka */}
        <div className="grid grid-cols-4 gap-4">
          <StatCard label="Request" nilai={formatRibuan(r?.total)} sub={`${formatRibuan(r?.per_tier?.light || 0)} light · ${formatRibuan(r?.per_tier?.heavy || 0)} heavy`} />
          <StatCard
            label="Biaya"
            nilai={formatDollar(r?.cost_usd)}
            sub={`≈ ${formatDolarKeRupiah(r?.cost_usd)} · ${formatRibuan(r?.rows_without_cost)} baris tanpa biaya`}
          />
          <StatCard label="Porsi heavy" nilai={formatPersen(porsiHeavy)} sub="dari keputusan auto" />
          <StatCard
            label="Cache ratio"
            nilai={formatPersen(r?.cache_ratio)}
            sub={`p50 ${formatMs(r?.latency_p50_ms)} · p95 ${formatMs(r?.latency_p95_ms)}`}
          />
        </div>

        {/* Porsi tier */}
        <div className="bg-surface border border-border rounded-lg p-4">
          <h2 className="text-[13px] font-medium text-muted mb-3">Porsi tier</h2>
          <div className="flex h-6 rounded overflow-hidden">
            {(["light", "heavy", "passthrough"]).map((t) => {
              const n = r?.per_tier?.[t] || 0;
              const warna = t === "light" ? "bg-tier-light" : t === "heavy" ? "bg-tier-heavy" : "bg-tier-pass";
              return n > 0 ? (
                <div key={t} className={`${warna} text-bg text-xs font-medium flex items-center justify-center`} style={{ width: `${(n / (r.total || 1)) * 100}%` }}>
                  {Math.round((n / (r.total || 1)) * 100)}%
                </div>
              ) : null;
            })}
          </div>
          <div className="flex gap-4 mt-2 text-xs text-muted">
            <span>■ light: {formatRibuan(r?.per_tier?.light || 0)}</span>
            <span>■ heavy: {formatRibuan(r?.per_tier?.heavy || 0)}</span>
            <span>■ passthrough: {formatRibuan(r?.per_tier?.passthrough || 0)}</span>
          </div>
        </div>

        <RequestLog rows={log} onLihatSemua={() => setHalaman("monitor")} />
      </div>
    </div>
  );
}
