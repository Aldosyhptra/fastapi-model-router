// Sidebar kiri (200px) — pengganti navbar atas. Dipanggil tiap view.
export default function Sidebar({ halaman, setHalaman, onLogout }) {
  const menu = [
    { id: "ringkasan", label: "Ringkasan", icon: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" },
    { id: "monitor", label: "Monitor", icon: "M4 6h16M4 12h16M4 18h16" },
    { id: "models", label: "Models", icon: "M12 8a2 2 0 100-4 2 2 0 000 4zM12 22a2 2 0 100-4 2 2 0 000 4zM12 15a2 2 0 100-4 2 2 0 000 4z" },
  ];

  return (
    <aside className="w-[200px] h-screen sticky top-0 flex flex-col bg-surface border-r border-border p-4">
      <div className="flex items-center gap-2 mb-6">
        <div className="w-8 h-8 rounded-md bg-primary/20 text-primary font-semibold flex items-center justify-center">R</div>
        <div>
          <div className="font-semibold leading-tight">Model Router</div>
          <div className="text-xs text-muted leading-tight">Dashboard</div>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {menu.map((m) => (
          <button
            key={m.id}
            onClick={() => setHalaman(m.id)}
            aria-current={halaman === m.id ? "page" : undefined}
            className={`flex items-center gap-2 px-3 h-9 rounded-md text-[13px] font-medium cursor-pointer
              ${halaman === m.id ? "bg-primary/15 text-primary" : "text-muted hover:bg-surface-2 hover:text-text"}`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d={m.icon} />
            </svg>
            {m.label}
          </button>
        ))}
      </nav>

      <button
        onClick={onLogout}
        className="mt-auto flex items-center gap-2 px-3 h-9 rounded-md text-[13px] font-medium text-muted hover:bg-surface-2 hover:text-error cursor-pointer"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
        </svg>
        Keluar
      </button>
    </aside>
  );
}
