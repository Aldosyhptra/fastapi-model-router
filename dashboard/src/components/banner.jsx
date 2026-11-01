// Pesan status: sukses (ok), peringatan (warn), atau galat (error).
const STYLE = {
  ok: "border-ok/40 bg-ok/10 text-ok",
  warn: "border-warn/40 bg-warn/10 text-warn",
  error: "border-error/40 bg-error/10 text-error",
};

export default function Banner({ jenis = "error", children }) {
  return (
    <div role="alert" className={`border rounded-md px-3 py-2 text-[13px] ${STYLE[jenis]}`}>
      {children}
    </div>
  );
}
