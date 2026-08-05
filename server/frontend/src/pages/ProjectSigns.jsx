import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { federation } from "@/api/federationClient";
import { Signpost, RefreshCw, Download, ExternalLink, MapPin, FlaskConical } from "lucide-react";
import PageHeader from "@/components/shared/PageHeader";
import StatCard from "@/components/shared/StatCard";
import EmptyState from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/use-toast";

const money = (amount, currency = "USD") => {
  const symbol = currency === "USD" ? "$" : "";
  const n = Number(amount) || 0;
  return `${symbol}${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

function SignCard({ sign, onPreview }) {
  const total = money(sign.total_amount, sign.currency);
  return (
    <Card className="p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-semibold text-foreground">{sign.title}</h3>
            {sign.synthetic && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-status-caution-fg/40 text-[11px] text-status-caution-fg">
                <FlaskConical className="h-3 w-3" /> Synthetic
              </span>
            )}
          </div>
          {sign.location && (
            <p className="text-sm text-muted-foreground flex items-center gap-1 mt-0.5">
              <MapPin className="h-3.5 w-3.5" /> {sign.location}
            </p>
          )}
        </div>
        <div className="text-right">
          <div className="text-xs text-muted-foreground uppercase tracking-wide">Total</div>
          <div className="text-lg font-semibold font-mono-id text-foreground">{total}</div>
        </div>
      </div>

      <ul className="flex flex-col gap-1.5">
        {sign.contributions.map((c) => (
          <li key={c.award_id} className="flex items-center justify-between text-sm border-t border-border pt-1.5">
            <div className="min-w-0">
              <div className="font-medium text-foreground truncate">{c.agency_name}</div>
              {c.officials.length > 0 && (
                <div className="text-xs text-muted-foreground truncate">
                  {c.officials.map((o) => o.name + (o.role ? ` (${o.role})` : "")).join(", ")}
                </div>
              )}
            </div>
            <span className="font-mono-id text-foreground shrink-0 ml-3">{money(c.amount, c.currency)}</span>
          </li>
        ))}
      </ul>

      <div className="flex items-center gap-2 mt-1">
        <Button variant="secondary" size="sm" onClick={() => onPreview(sign)}>
          <ExternalLink className="h-4 w-4 mr-1.5" /> Preview
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <a href={federation.projectSigns.htmlUrl(sign.project_id)} download={`${sign.project_id}.html`}>
            <Download className="h-4 w-4 mr-1.5" /> Download
          </a>
        </Button>
      </div>
    </Card>
  );
}

export default function ProjectSigns() {
  const qc = useQueryClient();
  const [preview, setPreview] = useState(null);
  const [generating, setGenerating] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["ProjectSigns"],
    queryFn: () => federation.projectSigns.list(),
    initialData: { count: 0, signs: [] },
  });

  const signs = data?.signs || [];
  const syntheticCount = signs.filter((s) => s.synthetic).length;

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await federation.projectSigns.generate(true);
      await qc.invalidateQueries({ queryKey: ["ProjectSigns"] });
      toast({
        title: "Signs generated",
        description: `${result.count} project sign(s) written to reports/signs.`,
      });
    } catch (err) {
      toast({
        title: "Could not generate signs",
        description: err?.message || "Request failed.",
        variant: "destructive",
      });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <PageHeader
        icon={Signpost}
        title="Project Signs"
        description="Consolidation placards generated from the federation aggregate — each project's funding contributions, officials, and amounts on one sign. Generated here without the CLI."
        actions={
          <Button onClick={handleGenerate} disabled={generating}>
            <RefreshCw className={`h-4 w-4 mr-2 ${generating ? "animate-spin" : ""}`} />
            {generating ? "Generating…" : "Generate signs"}
          </Button>
        }
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
        <StatCard label="Projects" value={signs.length} icon={Signpost} />
        <StatCard
          label="Total consolidated"
          value={money(signs.reduce((sum, s) => sum + (Number(s.total_amount) || 0), 0))}
        />
        <StatCard label="Synthetic" value={syntheticCount} icon={FlaskConical}
          alert={syntheticCount > 0} accent={syntheticCount > 0 ? "text-status-caution-fg" : "text-foreground"} />
      </div>

      {isLoading ? (
        <EmptyState icon={Signpost} title="Loading signs…" />
      ) : isError ? (
        <EmptyState icon={Signpost} title="Could not load signs"
          description="The aggregate may be unavailable. Run consolidation, then generate signs." />
      ) : signs.length === 0 ? (
        <EmptyState
          icon={Signpost}
          title="No project signs yet"
          description="Once the hub consolidates funding awards, click “Generate signs” to build a placard for each project."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {signs.map((sign) => (
            <SignCard key={sign.project_id} sign={sign} onPreview={setPreview} />
          ))}
        </div>
      )}

      <Dialog open={!!preview} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{preview?.title} — {preview?.location}</DialogTitle>
          </DialogHeader>
          {preview && (
            <iframe
              title={`sign-${preview.project_id}`}
              src={federation.projectSigns.htmlUrl(preview.project_id)}
              className="w-full rounded-lg border border-border"
              style={{ height: "70vh" }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
