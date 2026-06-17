import React, { useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import { useEntityData } from "@/hooks/useEntityData";
import { TASK_PROGRAM_ORDER, normalizeTaskStatus } from "@/lib/task-utils";
import { BarChart3 } from "lucide-react";

// Per-program task completion breakdown: Active (Backlog/Ready/Blocked), In Progress (InProgress/Review), Done.
const SERIES = [
  { key: "active", label: "Active", color: "hsl(var(--chart-1))" },
  { key: "inProgress", label: "In Progress", color: "hsl(var(--chart-3))" },
  { key: "done", label: "Completed", color: "hsl(var(--chart-2))" },
];

function bucketOf(status) {
  const s = normalizeTaskStatus(status);
  if (s === "Done") return "done";
  if (s === "InProgress" || s === "Review") return "inProgress";
  if (s === "Deferred") return null; // exclude from completion view
  return "active";
}

export default function ProgramTaskChart() {
  const { rows: tasks, isLoading } = useEntityData("FederationTasks");

  const data = useMemo(() => {
    return TASK_PROGRAM_ORDER.filter((p) => p.key.startsWith("prog")).map((p) => {
      const scoped = tasks.filter((t) => t.program_id === p.key);
      const row = { name: p.label.replace("-PR", ""), active: 0, inProgress: 0, done: 0, total: 0 };
      scoped.forEach((t) => {
        const b = bucketOf(t.status);
        if (b) { row[b] += 1; row.total += 1; }
      });
      row.pct = row.total ? Math.round((row.done / row.total) * 100) : 0;
      return row;
    });
  }, [tasks]);

  const hasData = data.some((d) => d.total > 0);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 className="h-4 w-4 text-sky-300" />
        <h3 className="text-sm font-semibold">Task Completion by Module</h3>
      </div>
      <p className="text-xs text-muted-foreground mb-4">
        Active, in-progress, and completed task counts per research program. Completion % shown on hover.
      </p>

      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">Loading…</div>
      ) : !hasData ? (
        <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
          No tasks assigned to programs yet.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              cursor={{ fill: "hsl(var(--accent))", opacity: 0.4 }}
              contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
              formatter={(value, name, item) => {
                if (name === "Completed") return [`${value} (${item.payload.pct}%)`, name];
                return [value, name];
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {SERIES.map((s) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} radius={s.key === "done" ? [4, 4, 0, 0] : 0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}