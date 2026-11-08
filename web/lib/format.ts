export const mg = (n: number | undefined, d?: number) => {
  if (n == null || Number.isNaN(n)) return "–";
  const digits = d ?? (n < 0.1 ? 3 : n < 1 ? 2 : 1);
  return `${n.toFixed(digits)} mg`;
};
export const pct = (n: number | undefined, d = 1) => (n == null ? "–" : `${n.toFixed(d)}%`);
export const time = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export const ago = (iso: string) => {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
};
export const todayKey = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export const FACTOR_LABEL: Record<string, string> = {
  polyphenols: "Polyphenols (tea, coffee)",
  phytate: "Phytate",
  calcium: "Calcium",
  vitamin_c: "Vitamin C",
  mfp: "Meat, fish, poultry",
  floor: "Minimum floor",
};
