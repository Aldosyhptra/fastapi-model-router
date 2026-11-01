import { useEffect, useRef, useState } from "react";
import Sidebar from "../components/sidebar.jsx";
import DecisionTable from "../components/decisiontable.jsx";
import Banner from "../components/banner.jsx";
import { fetchDecisions } from "../lib/api.jsx";

// Monitor: tabel keputusan live, polling 2 detik (F3).
export default function Monitor({ halaman, setHalaman, onLogout }) {
  const [rows, setRows] = useState([]);
  const [jeda, setJeda] = useState(false);
  const [mataUang, setMataUang] = useState("usd");
  const [galat, setGalat] = useState(false);
  const offset = useRef(0);

  useEffect(() => {
    if (jeda) return;
    let hidup = true;

    const poll = async () => {
      const d = await fetchDecisions(offset.current, 100);
      if (!hidup) return;
      if (d.rows.length > 0) {
        setRows((lama) => {
          const gabung = [...d.rows, ...lama];
          return gabung.slice(0, 100); // tampilkan 100 baris terakhir
        });
      }
      // offset terus maju supaya polling berikutnya hanya mengambil baris baru
      if (d.offset > 0) offset.current = d.offset;
    };

    poll();
    const t = setInterval(poll, 2000);
    return () => {
      hidup = false;
      clearInterval(t);
    };
  }, [jeda]);

  return (
    <div className="flex">
      <Sidebar halaman={halaman} setHalaman={setHalaman} onLogout={onLogout} />
      <div className="flex-1 p-6 space-y-4 max-w-[1280px]">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Monitor</h1>
          <span className="text-[13px] text-muted">
            {jeda ? "Dijeda" : "Live"} · {rows.length} baris
          </span>
          <div className="ml-auto flex gap-1">
            <button
              onClick={() => setJeda((j) => !j)}
              className="h-8 px-3 rounded-md text-[13px] bg-surface-2 border border-border hover:border-primary cursor-pointer"
            >
              {jeda ? "Lanjutkan" : "Jeda"}
            </button>
            <button
              onClick={() => setMataUang((m) => (m === "usd" ? "idr" : "usd"))}
              className="h-8 px-3 rounded-md text-[13px] bg-surface-2 border border-border hover:border-primary cursor-pointer"
            >
              {mataUang === "usd" ? "USD" : "IDR"}
            </button>
          </div>
        </div>

        {galat && <Banner jenis="warn">Koneksi terputus — menampilkan data terakhir yang diterima.</Banner>}

        <DecisionTable rows={rows} mataUang={mataUang} />
      </div>
    </div>
  );
}
