import TierBadge from "./tierbadge";
import { formatJam, formatRibuan, formatDollar, formatDolarKeRupiah, formatMs } from "../lib/format";

// Log request terakhir di Ringkasan (6 baris).
export default function RequestLog({ rows, onLihatSemua }) {
  return (
    <div className="bg-surface border border-border rounded-lg">
      <div className="flex items-center justify-between px-4 py-3">
        <h2 className="text-[13px] font-medium text-muted">
          Log request terakhir <span aria-hidden="true" className="text-ok">●</span>
        </h2>
        <button
          onClick={onLihatSemua}
          className="text-[13px] text-primary hover:underline cursor-pointer"
        >
          Semua log → Monitor
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-muted text-left border-y border-border">
              <th scope="col" className="px-4 py-2 font-medium">Waktu</th>
              <th scope="col" className="px-4 py-2 font-medium">Tier</th>
              <th scope="col" className="px-4 py-2 font-medium">Model</th>
              <th scope="col" className="px-4 py-2 font-medium text-right">Input</th>
              <th scope="col" className="px-4 py-2 font-medium text-right">Cached</th>
              <th scope="col" className="px-4 py-2 font-medium text-right">Output</th>
              <th scope="col" className="px-4 py-2 font-medium text-right">Biaya</th>
              <th scope="col" className="px-4 py-2 font-medium text-right">Latensi</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan="8" className="px-4 py-6 text-center text-muted">Belum ada request.</td>
              </tr>
            )}
            {rows.map((r, i) => {
              const u = r.usage || {};
              const cached = u.prompt_tokens_details?.cached_tokens;
              return (
                <tr key={i} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2 font-mono tabular-nums text-muted">{formatJam(r.ts)}</td>
                  <td className="px-4 py-2"><TierBadge tier={r.tier} /></td>
                  <td className="px-4 py-2 font-mono text-xs">{r.model || "n/a"}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">{formatRibuan(u.prompt_tokens)}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">{formatRibuan(cached)}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">{formatRibuan(u.completion_tokens)}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {u.cost != null ? (
                      <>
                        {formatDollar(u.cost)}
                        <span className="text-muted"> ({formatDolarKeRupiah(u.cost)})</span>
                      </>
                    ) : "n/a"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums text-muted">{formatMs(r.latency_ms)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
