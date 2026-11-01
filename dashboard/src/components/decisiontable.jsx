import TierBadge from "./tierbadge";
import { formatJam, formatRibuan, formatDollar, formatPersen, formatMs } from "../lib/format";

// Tabel keputusan lengkap untuk Monitor. baris terbaru di atas.
export default function DecisionTable({ rows, mataUang }) {
  const biaya = (cost) => {
    if (cost == null) return "n/a";
    return mataUang === "idr" ? `Rp${Math.round(cost * 16000).toLocaleString("id-ID")}` : formatDollar(cost);
  };

  return (
    <div className="bg-surface border border-border rounded-lg overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-muted text-left border-b border-border">
            <th scope="col" className="px-4 py-2 font-medium">Waktu (WIB)</th>
            <th scope="col" className="px-4 py-2 font-medium">Tier</th>
            <th scope="col" className="px-4 py-2 font-medium">Model</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Skor</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Input</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Cached</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Output</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Biaya</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Latensi</th>
            <th scope="col" className="px-4 py-2 font-medium text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan="10" className="px-4 py-6 text-center text-muted">Belum ada keputusan.</td>
            </tr>
          )}
          {rows.map((r, i) => {
            const u = r.usage || {};
            const cached = u.prompt_tokens_details?.cached_tokens;
            const cacheRatio = u.prompt_tokens ? (cached || 0) / u.prompt_tokens : null;
            const error = r.status >= 400;
            return (
              <tr
                key={i}
                title={r.reason || ""}
                className={`border-b border-border/50 last:border-0 hover:bg-surface-2 ${error ? "border-l-2 border-l-error" : ""}`}
              >
                <td className="px-4 py-2 font-mono tabular-nums text-muted">{formatJam(r.ts)}</td>
                <td className="px-4 py-2"><TierBadge tier={r.tier} /></td>
                <td className="px-4 py-2 font-mono text-xs">{r.model || "n/a"}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">{r.score ?? "n/a"}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">{formatRibuan(u.prompt_tokens)}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">
                  {formatRibuan(cached)}
                  {cacheRatio != null && <span className="text-muted"> ({formatPersen(cacheRatio)})</span>}
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">{formatRibuan(u.completion_tokens)}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">{biaya(u.cost)}</td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-muted">{formatMs(r.latency_ms)}</td>
                <td className={`px-4 py-2 text-right font-mono tabular-nums ${error ? "text-error" : "text-ok"}`}>
                  {r.status ?? "n/a"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
