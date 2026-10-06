import React, { useEffect, useState } from "react";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

function State({ value }) {
  return <span className="rounded border px-2 py-0.5 text-xs font-medium">{value || "UNKNOWN"}</span>;
}

const PLANES = {
  debt: {
    label: "Debt issuance",
    statusUrl: "/api/moneysweep/leaderboards/status",
    topUrl: "/api/moneysweep/leaderboards/top?category=debt_issuance&limit=25",
    title: "Certified Public Debt Issuance",
    measure: "DEBT_ISSUED_PAR",
    amountLabel: "Par amount",
    boundary: "Public debt issued at par only; not outstanding debt, debt service, expenditure, or cash received.",
  },
  asg: {
    label: "ASG emergency purchases",
    statusUrl: "/api/moneysweep/asg-leaderboards/status",
    topUrl: "/api/moneysweep/asg-leaderboards/top?limit=25",
    title: "ASG Emergency Purchases — Source-Native IDs",
    measure: "ASG_EMERGENCY_PURCHASE_COST",
    amountLabel: "Purchase cost",
    boundary: "Ranks only purchases carrying an explicit ASG Licitador ID. Name-only and missing-vendor rows remain outside this identity-bounded ranking; this is not total ASG emergency spending by identified vendor.",
  },
};

export default function MoneySweepLeaderboardsTab() {
  const [plane, setPlane] = useState("debt");
  const [states, setStates] = useState({});
  const [rankings, setRankings] = useState({});
  const [errors, setErrors] = useState({});

  useEffect(() => {
    let alive = true;
    for (const [key, spec] of Object.entries(PLANES)) {
      fetch(spec.statusUrl)
        .then((response) => response.json())
        .then((body) => {
          if (!alive) return;
          setStates((prev) => ({ ...prev, [key]: body }));
          if (body.state !== "PASS") return null;
          return fetch(spec.topUrl)
            .then(async (response) => {
              const payload = await response.json();
              if (!response.ok) throw new Error(payload?.detail?.reason || `HTTP ${response.status}`);
              return payload;
            })
            .then((payload) => alive && setRankings((prev) => ({ ...prev, [key]: payload })));
        })
        .catch((err) => alive && setErrors((prev) => ({ ...prev, [key]: err.message })));
    }
    return () => { alive = false; };
  }, []);

  const spec = PLANES[plane];
  const status = states[plane];
  const ranking = rankings[plane];
  const error = errors[plane];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="MoneySweep certified leaderboard plane">
        {Object.entries(PLANES).map(([key, value]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={plane === key}
            onClick={() => setPlane(key)}
            className={`rounded border px-3 py-1.5 text-sm ${plane === key ? "bg-primary text-primary-foreground" : "bg-card"}`}
          >
            {value.label}
          </button>
        ))}
      </div>

      {error && (
        <div role="alert" className="rounded border border-destructive p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {!error && !status && (
        <div className="p-4 text-sm text-muted-foreground">Checking certified MoneySweep leaderboard package…</div>
      )}

      {!error && status && status.state !== "PASS" && (
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">{spec.title}</h3>
            <State value={status.state} />
          </div>
          <p className="text-sm text-muted-foreground">
            This plane is fail-closed until TheHub trusts the exact MoneySweep receipt, release, scope, and package SHA-256 values.
          </p>
          {status.reason && <p className="text-xs text-muted-foreground">{status.reason}</p>}
        </div>
      )}

      {!error && status?.state === "PASS" && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3">
            <div>
              <h3 className="font-semibold">{spec.title}</h3>
              <p className="text-xs text-muted-foreground">
                {spec.measure}. TheHub displays MoneySweep-certified rows without recomputing totals, rank, identity, or geometry.
              </p>
              <p className="max-w-3xl text-xs text-muted-foreground">{ranking?.scopeBoundary || spec.boundary}</p>
              <p className="text-xs text-muted-foreground">Scope: {status.scopeId || "unresolved"}</p>
              {plane === "asg" && (
                <p className="text-xs text-muted-foreground">
                  Full source accounting: {status.inputRecords ?? "?"} records = {status.outOfScopeRecords ?? "?"} explicit identity exclusions + {status.retainedRecords ?? "?"} retained source-native rows.
                </p>
              )}
              {status.consumerPackageSha256 && (
                <p
                  className="max-w-xl truncate font-mono text-[11px] text-muted-foreground"
                  title={status.consumerPackageSha256}
                >
                  Package SHA-256: {status.consumerPackageSha256}
                </p>
              )}
            </div>
            <State value="PASS" />
          </div>

          <div className="overflow-x-auto rounded-lg border border-border bg-card">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="p-2">Rank</th>
                  <th className="p-2">{plane === "asg" ? "ASG supplier" : "Issuer"}</th>
                  <th className="p-2 text-right">{spec.amountLabel}</th>
                  <th className="p-2">Identity</th>
                </tr>
              </thead>
              <tbody>
                {(ranking?.rows || []).map((row) => (
                  <tr key={`${row.entityId}:${row.currency}`} className="border-t border-border">
                    <td className="p-2">#{row.rank}</td>
                    <td className="p-2">
                      <div className="font-medium">{row.entityDisplayName}</div>
                      <div className="font-mono text-xs text-muted-foreground">{row.entityId}</div>
                      {plane === "asg" && row.recordCount != null && (
                        <div className="text-xs text-muted-foreground">{row.recordCount} retained purchase{row.recordCount === 1 ? "" : "s"}</div>
                      )}
                    </td>
                    <td className="p-2 text-right tabular-nums">
                      {row.currency === "USD" ? money.format(row.metricValue) : `${row.metricValue} ${row.currency}`}
                    </td>
                    <td className="p-2"><State value={row.entityResolutionState} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!ranking?.rows?.length && (
              <div className="p-4 text-sm text-muted-foreground">No certified rows are present in the promoted package.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
