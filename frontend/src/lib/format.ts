export function money(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  });
}

export function scoreClass(score: number): string {
  if (score >= 0.9) return "bg-red-950 text-red-300 border-red-900";
  if (score >= 0.7) return "bg-amber-950 text-amber-300 border-amber-900";
  return "bg-slate-800 text-slate-300 border-slate-700";
}