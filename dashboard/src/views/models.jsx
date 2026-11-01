import { useEffect, useState } from "react";
import Sidebar from "../components/sidebar.jsx";
import TierForm from "../components/tierform.jsx";
import Modal from "../components/modal.jsx";
import Banner from "../components/banner.jsx";
import { fetchTiers, updateTiers } from "../lib/api.jsx";

// Models: ganti model light/heavy per tier, simpan ke config/tiers.json (F4).
export default function Models({ halaman, setHalaman, onLogout }) {
  const [nilai, setNilai] = useState(null);
  const [konfirmasi, setKonfirmasi] = useState(null); // {light, heavy} yang menunggu persetujuan
  const [pesan, setPesan] = useState(null); // {jenis, teks}

  useEffect(() => {
    fetchTiers().then((t) => t && setNilai(t));
  }, []);

  const handleSimpan = (light, heavy) => {
    if (!light || !heavy) {
      setPesan({ jenis: "error", teks: "Nama model tidak boleh kosong." });
      return;
    }
    setKonfirmasi({ light, heavy });
  };

  const handleKonfirmasi = async () => {
    try {
      const hasil = await updateTiers(konfirmasi.light, konfirmasi.heavy);
      setNilai({ light: hasil.light, heavy: hasil.heavy, source: "config/tiers.json" });
      setPesan({ jenis: "ok", teks: "Tersimpan. Request berikutnya memakai model baru." });
    } catch (err) {
      setPesan({ jenis: "error", teks: err.message });
    } finally {
      setKonfirmasi(null);
    }
  };

  return (
    <div className="flex">
      <Sidebar halaman={halaman} setHalaman={setHalaman} onLogout={onLogout} />
      <div className="flex-1 p-6 space-y-6 max-w-[1280px]">
        <h1 className="text-xl font-semibold">Models</h1>

        {pesan && <Banner jenis={pesan.jenis}>{pesan.teks}</Banner>}

        {nilai ? (
          <>
            <TierForm nilai={nilai} onSimpan={handleSimpan} />
            <p className="text-xs text-muted max-w-md">
              Nilai tersimpan di <code className="font-mono">config/tiers.json</code> (sumber: {nilai.source}).
              Mengganti model akan memecah cache prompt untuk request berikutnya.
            </p>
          </>
        ) : (
          <p className="text-muted">Memuat…</p>
        )}

        <Modal
          isOpen={!!konfirmasi}
          onClose={() => setKonfirmasi(null)}
          title="Simpan perubahan model?"
        >
          <p className="text-[13px] text-muted">
            Light → <span className="font-mono text-text">{konfirmasi?.light}</span>
            <br />
            Heavy → <span className="font-mono text-text">{konfirmasi?.heavy}</span>
            <br />
            <br />
            Penggantian model memecah cache prompt sehingga request awal bisa lebih lambat.
          </p>
          <div className="flex gap-2 mt-6">
            <button
              onClick={handleKonfirmasi}
              className="h-9 px-4 rounded-md bg-primary text-bg text-[13px] font-medium hover:opacity-90 cursor-pointer"
            >
              Ya, simpan
            </button>
            <button
              onClick={() => setKonfirmasi(null)}
              className="h-9 px-4 rounded-md bg-surface-2 border border-border text-[13px] hover:border-primary cursor-pointer"
            >
              Batal
            </button>
          </div>
        </Modal>
      </div>
    </div>
  );
}
