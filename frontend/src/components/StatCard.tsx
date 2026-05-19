type Props = { label: string; value: number | string; tone?: "ok" | "warn" | "err" | "accent" };

const toneColor: Record<NonNullable<Props["tone"]>, string> = {
  ok: "text-ok",
  warn: "text-warn",
  err: "text-err",
  accent: "text-accent",
};

export function StatCard({ label, value, tone = "accent" }: Props) {
  return (
    <div className="bg-slab border border-edge rounded-lg px-5 py-4 min-w-[150px]">
      <div className={`text-3xl font-bold ${toneColor[tone]}`}>{value}</div>
      <div className="text-xs text-muted uppercase tracking-wide mt-1">{label}</div>
    </div>
  );
}
