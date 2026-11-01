// Kartu angka besar di Ringkasan.
export default function StatCard({ label, nilai, sub }) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="text-[13px] font-medium text-muted">{label}</div>
      <div className="text-[28px] font-semibold font-mono tabular-nums leading-tight mt-1">{nilai}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}
