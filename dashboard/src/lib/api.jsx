// Semua panggilan API dashboard dalam satu tempat.
// Gagal mengambil data → return kosong supaya halaman tetap tampil (lihat docs/DESIGN.md).

export async function fetchSession() {
  try {
    const response = await fetch("/api/session", { credentials: "include" });
    return response.ok;
  } catch (err) {
    console.error("Error:", err);
    return false;
  }
}

export async function login(password) {
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Login gagal");
    return result;
  } catch (error) {
    console.error("Login error:", error);
    throw error;
  }
}

export async function logout() {
  try {
    await fetch("/api/logout", { method: "POST", credentials: "include" });
  } catch (error) {
    console.error("Logout error:", error);
  }
}

export async function fetchSummary(window = "24h") {
  try {
    const response = await fetch(`/api/summary?window=${window}`, { credentials: "include" });
    if (!response.ok) throw new Error("Gagal mengambil ringkasan");
    return await response.json();
  } catch (err) {
    console.error("Error:", err);
    return null;
  }
}

export async function fetchDecisions(after = 0, limit = 100) {
  try {
    const response = await fetch(`/api/decisions?after=${after}&limit=${limit}`, { credentials: "include" });
    if (!response.ok) throw new Error("Gagal mengambil log");
    return await response.json();
  } catch (err) {
    console.error("Error:", err);
    return { rows: [], offset: after };
  }
}

export async function fetchStatus() {
  try {
    const response = await fetch("/api/status", { credentials: "include" });
    if (!response.ok) throw new Error("Gagal mengambil status");
    return await response.json();
  } catch (err) {
    console.error("Error:", err);
    return null;
  }
}

export async function fetchTiers() {
  try {
    const response = await fetch("/api/tiers", { credentials: "include" });
    if (!response.ok) throw new Error("Gagal mengambil model");
    return await response.json();
  } catch (err) {
    console.error("Error:", err);
    return null;
  }
}

export async function updateTiers(light, heavy) {
  try {
    const response = await fetch("/api/tiers", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ light, heavy }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Gagal menyimpan");
    return result;
  } catch (error) {
    console.error("Update tiers error:", error);
    throw error;
  }
}
