import React, { useEffect, useState } from "react";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function State({ value }) {
  return <span className="rounded border px-2 py-0.5 text-xs font-medium">{value || "UNKNOWN"}</span>;
}

export default function MoneySweepLeaderboardsTab() {
  const [status, setStatus] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    fetch("/api/moneysweep/leaderboards/status")
      .then((response) => response.json())
      .then((body) => {
        if (!alive) return;
        setStatus(body);
        if (body.state !== "PASS") return null;
        return fetch("/api/moneysweep/leaderboards/top?category=contract_award&limit=25")
          .then(async (response) => {
            const payload = await response.json();
            if (!response.ok) throw new Error(payload?.detail?.reason || `HTTP ${response.status}`);
            return payload;
          })
          .then((payload) => alive && setRanking(payload));
      })
      .catch((err) => alive && setError(err.message));
    return () => { alive = false; };
  }, []);

  if (error) {
    return <div role="alert" className="rounded border border-destructive p-4 text-sm text-destructive">{error}</div>;
  }

  if (!status) return <div className="p-4 text-sm text-muted-foreground">Checking certified MoneySweep leaderboard package…</div>;

  if (status.state !== "PASS") {
    return (
      <div className="space-y-3 rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">Financial Leaderboards</h3>
          <State value={status.state} />
        </div>
        <p className="text-sm text-muted-foreground">
          Product promotion is fail-closed until MoneySweep supplies a certified frozen package and TheHub trusts the exact receipt and release hashes.
        </p>
        {status.reason && <p className="text-xs text-muted-foreground">{status.reason}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3">
        <div>
          <h3 className="font-semibold">Certified Financial Leaderboards</h3>
          <p className="text-xs text-muted-foreground">TheHub displays producer-certified MoneySweep rows without recomputing financial totals or rank.</p>
        </div>
        <State value="PASS" />
      </div>
      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr><th className="p-2">Rank</th><th className="p-2">Entity</th><th className="p-2 text-right">Value</th><th className="p-2">Identity</th></tr>
          </thead>
          <tbody>
            {(ranking?.rows || []).map((row) => (
              <tr key={`${row.entityId}:${row.currency}`} className="border-t border-border">
                <td className="p-2">#{row.rank}</td>
                <td className="p-2"><div className="font-medium">{row.entityDisplayName}</div><div className="font-mono text-xs text-muted-foreground">{row.entityId}</div></td>
                <td className="p-2 text-right tabular-nums">{row.currency === "USD" ? money.format(row.metricValue) : `${row.metricValue} ${row.currency}`}</td>
                <td className="p-2"><State value={row.entityResolutionState} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {!ranking?.rows?.length && <div className="p-4 text-sm text-muted-foreground">No certified rows are present in the promoted package.</div>}
      </div>
    </div>
  );
}
