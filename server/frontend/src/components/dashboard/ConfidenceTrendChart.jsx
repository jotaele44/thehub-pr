import React, { useMemo } from "react";
import { useCrossover } from "@/hooks/useCrossover";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { TrendingUp, Info } from "lucide-react";

const DAYS = 30;
const BANDS = [
  { key: "High", color: "hsl(var(--chart-2))" },
  { key: "Medium", color: "hsl(var(--chart-1))" },
  { key: "Low", color: "hsl(var(--chart-3))" },
];

// Build a 30-day cumulative trend of correlation confidence bands.
// Only crossovers carrying a real creation timestamp (stored links / reviews) are trended —
// runtime candidates have no timestamp and are excluded to avoid fabricating history.
function buildSeries(crossovers) {
  const dated = crossovers
    .map((c) => ({ band: c.confidence_band, date: c._created_date || c.created_date }))
    .filter((c) => c.date && (c.band === "High" || c.band === "Medium" || c.band === "Low"))
    .map((c) => ({ band: c.band, t: new Date(c.date).getTime() }))
    .filter((c) => !Number.isNaN(c.t));

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = today.getTime() - (DAYS - 1) * 86400000;

  const days = [];
  for (let i = 0; i < DAYS; i++) {
    const dayStart = start + i * 86400000;
    const dayEnd = dayStart + 86400000;
    // Cumulative: everything created up to the end of this day.
    const upTo = dated.filter((c) => c.t < dayEnd);
    days.push({
      date: new Date(dayStart).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      High: upTo.filter((c) => c.band === "High").length,
      Medium: upTo.filter((c) => c.band === "Medium").length,
      Low: upTo.filter((c) => c.band === "Low").length,
    });
  }
  return { days, datedCount: dated.length };
}

export default function ConfidenceTrendChart() {
  const { crossovers, isLoading } = useCrossover();
  const { days, datedCount } = useMemo(() => buildSeries(crossovers), [crossovers]);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-3 mb-1">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-status-info-fg" />
          <h3 className="text-sm font-semibold">Correlation Confidence Trend</h3>
        </div>
        <span className="text-[11px] text-muted-foreground">Last {DAYS} days · cumulative</span>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Shows how the body of confidence-banded correlations has shifted over time — a rising High band relative to Low indicates improving data quality.
      </p>

      {datedCount === 0 ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-10 justify-center">
          <Info className="h-4 w-4" />
          {isLoading ? "Loading correlation history…" : "No timestamped correlations yet — trend appears as stored crossover links accumulate."}
        </div>
      ) : (
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={days} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                {BANDS.map((b) => (
                  <linearGradient key={b.key} id={`grad-${b.key}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={b.color} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={b.color} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} interval={Math.floor(DAYS / 6)} tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} width={32} />
              <Tooltip
                contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "hsl(var(--foreground))" }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {BANDS.map((b) => (
                <Area key={b.key} type="monotone" dataKey={b.key} stroke={b.color} strokeWidth={2} fill={`url(#grad-${b.key})`} stackId="1" />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}