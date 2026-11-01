import { useState } from "react";

// Dua input model (light & heavy) + tombol simpan.
export default function TierForm({ nilai, onSimpan }) {
  const [light, setLight] = useState(nilai.light);
  const [heavy, setHeavy] = useState(nilai.heavy);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSimpan(light.trim(), heavy.trim());
      }}
      className="bg-surface border border-border rounded-lg p-4 max-w-md"
    >
      <label className="block text-[13px] font-medium text-muted mb-1" htmlFor="model-light">
        Model light
      </label>
      <input
        id="model-light"
        value={light}
        onChange={(e) => setLight(e.target.value)}
        className="w-full h-9 px-3 rounded-md bg-surface-2 border border-border text-[13px] font-mono focus:outline-none focus:border-primary"
      />

      <label className="block text-[13px] font-medium text-muted mb-1 mt-4" htmlFor="model-heavy">
        Model heavy
      </label>
      <input
        id="model-heavy"
        value={heavy}
        onChange={(e) => setHeavy(e.target.value)}
        className="w-full h-9 px-3 rounded-md bg-surface-2 border border-border text-[13px] font-mono focus:outline-none focus:border-primary"
      />

      <button
        type="submit"
        className="mt-4 h-9 px-4 rounded-md bg-primary text-bg text-[13px] font-medium hover:opacity-90 cursor-pointer"
      >
        Simpan
      </button>
    </form>
  );
}
