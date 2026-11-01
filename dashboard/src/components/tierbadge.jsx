// Badge tier: warna + teks (bukan warna saja).
const STYLE = {
  light: "bg-tier-light/15 text-tier-light",
  heavy: "bg-tier-heavy/15 text-tier-heavy",
  passthrough: "bg-tier-pass/15 text-tier-pass",
};

export default function TierBadge({ tier }) {
  return (
    <span className={`inline-block px-2 h-5 leading-5 rounded text-xs font-medium ${STYLE[tier] || STYLE.passthrough}`}>
      {tier || "n/a"}
    </span>
  );
}
