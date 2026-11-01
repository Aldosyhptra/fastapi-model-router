import { test } from "node:test";
import assert from "node:assert/strict";
import {
  formatRibuan,
  formatDollar,
  formatRupiah,
  formatDolarKeRupiah,
  formatPersen,
  formatJam,
  KURS_IDR,
} from "./format.js";

test("ribuan pakai titik", () => {
  assert.equal(formatRibuan(79847), "79.847");
});

test("dollar pakai koma desimal Indonesia", () => {
  assert.equal(formatDollar(0.84), "$0,84");
});

test("rupiah tanpa desimal", () => {
  assert.equal(formatRupiah(13440), "Rp13.440");
});

test("dolar ke rupiah memakai kurs", () => {
  assert.equal(formatDolarKeRupiah(1), formatRupiah(KURS_IDR));
});

test("data kosong ditulis n/a", () => {
  assert.equal(formatRibuan(null), "n/a");
  assert.equal(formatDollar(undefined), "n/a");
  assert.equal(formatPersen(null), "n/a");
  assert.equal(formatJam(null), "n/a");
});

test("persen satu desimal", () => {
  assert.equal(formatPersen(0.9236), "92,4%");
});
