import { useEffect, useState } from "react";
import { fetchSession, logout } from "./lib/api.jsx";
import Login from "./views/login.jsx";
import Ringkasan from "./views/ringkasan.jsx";
import Monitor from "./views/monitor.jsx";
import Models from "./views/models.jsx";

export default function App() {
  // null = belum dicek, false = belum login, true = sudah login
  const [sudahLogin, setSudahLogin] = useState(null);
  const [halaman, setHalaman] = useState("ringkasan");

  useEffect(() => {
    fetchSession().then((ok) => setSudahLogin(ok));
  }, []);

  const handleLogout = async () => {
    await logout();
    setSudahLogin(false);
  };

  if (sudahLogin === null) return <p className="p-8 text-muted">Memuat…</p>;
  if (!sudahLogin) return <Login onLogin={() => setSudahLogin(true)} />;

  return (
    <div className="flex min-h-screen">
      <main className="flex-1 p-6">
        {halaman === "ringkasan" && <Ringkasan halaman={halaman} setHalaman={setHalaman} onLogout={handleLogout} />}
        {halaman === "monitor" && <Monitor halaman={halaman} setHalaman={setHalaman} onLogout={handleLogout} />}
        {halaman === "models" && <Models halaman={halaman} setHalaman={setHalaman} onLogout={handleLogout} />}
      </main>
    </div>
  );
}
