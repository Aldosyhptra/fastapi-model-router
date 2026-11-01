import { useState } from "react";
import { login } from "../lib/api.jsx";
import Banner from "../components/banner.jsx";

// Halaman login: satu kolom password (F1).
export default function Login({ onLogin }) {
  const [password, setPassword] = useState("");
  const [galat, setGalat] = useState("");
  const [sibuk, setSibuk] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSibuk(true);
    setGalat("");
    try {
      await login(password);
      onLogin();
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-surface border border-border rounded-xl p-6">
        <h1 className="text-xl font-semibold">Model Router</h1>
        <p className="text-[13px] text-muted mt-1 mb-6">Masukkan password dashboard.</p>

        {galat && <div className="mb-4"><Banner jenis="error">{galat}</Banner></div>}

        <label className="block text-[13px] font-medium text-muted mb-1" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          className="w-full h-9 px-3 rounded-md bg-surface-2 border border-border text-[13px] focus:outline-none focus:border-primary"
        />

        <button
          type="submit"
          disabled={sibuk || password.length === 0}
          className="mt-4 w-full h-9 rounded-md bg-primary text-bg text-[13px] font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer"
        >
          {sibuk ? "Memeriksa…" : "Masuk"}
        </button>
      </form>
    </div>
  );
}
