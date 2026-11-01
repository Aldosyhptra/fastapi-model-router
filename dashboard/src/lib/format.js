// Format angka Indonesia, WIB, dan biaya dua mata uang (docs/DESIGN.md).

export const KURS_IDR = 16000; // perkiraan, bisa diubah di satu tempat ini

export function formatRibuan(n) {
  return n == null ? "n/a" : n.toLocaleString("id-ID");
}

export function formatDollar(n) {
  return n == null
    ? "n/a"
    : "$" + n.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatRupiah(n) {
  return n == null ? "n/a" : "Rp" + Math.round(n).toLocaleString("id-ID");
}

export function formatDolarKeRupiah(n) {
  return n == null ? "n/a" : formatRupiah(n * KURS_IDR);
}

export function formatPersen(n) {
  return n == null
    ? "n/a"
    : (n * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + "%";
}

export function formatJam(detik) {
  return detik == null
    ? "n/a"
    : new Date(detik * 1000).toLocaleTimeString("id-ID", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Jakarta",
      });
}

export function formatMs(n) {
  return n == null ? "n/a" : n.toLocaleString("id-ID") + " ms";
}
