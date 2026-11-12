export function toNum(val: string | number | null | undefined): number {
  if (val === null || val === undefined || val === "") return 0;
  const n = typeof val === "number" ? val : Number(val);
  return Number.isFinite(n) ? n : 0;
}

export function formatCurrencyExact(
  val: string | number | null | undefined,
  showPlus = false,
): string {
  if (val === null || val === undefined) return "—";
  const num = toNum(val);
  const abs = Math.abs(num);
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(abs);
  if (num < 0) return `-${formatted}`;
  if (num > 0 && showPlus) return `+${formatted}`;
  return formatted;
}

export function formatCurrencyCompact(
  val: string | number | null | undefined,
  showPlus = false,
): string {
  if (val === null || val === undefined) return "—";
  const num = toNum(val);
  const abs = Math.abs(num);
  let out: string;
  if (abs >= 1_000_000_000) {
    out = `$${(abs / 1_000_000_000).toFixed(2)}B`;
  } else if (abs >= 1_000_000) {
    out = `$${(abs / 1_000_000).toFixed(2)}M`;
  } else if (abs >= 1_000) {
    out = `$${(abs / 1_000).toFixed(1)}K`;
  } else {
    out = `$${abs.toFixed(2)}`;
  }
  if (num < 0) return `-${out}`;
  if (num > 0 && showPlus) return `+${out}`;
  return out;
}

export function formatPct(
  val: string | number | null | undefined,
  showPlus = false,
): string {
  if (val === null || val === undefined) return "—";
  const num = toNum(val);
  const abs = Math.abs(num).toFixed(2);
  if (num < 0) return `-${abs}%`;
  if (num > 0 && showPlus) return `+${abs}%`;
  return `${abs}%`;
}
