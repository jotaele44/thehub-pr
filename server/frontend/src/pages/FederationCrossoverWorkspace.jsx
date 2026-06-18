import React from "react";
import { useCrossover } from "@/hooks/useCrossover";
import { exportCrossoversCsv } from "@/lib/crossover-export";
import PageHeader from "@/components/shared/PageHeader";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import CrossoverSummary from "@/components/crossover/CrossoverSummary";
import CrossoverMatrix from "@/components/crossover/CrossoverMatrix";
import CrossoverFilters from "@/components/crossover/CrossoverFilters";
import CrossoverCard from "@/components/crossover/CrossoverCard";
import PairPanel from "@/components/crossover/PairPanel";
import ConvergenceView from "@/components/crossover/ConvergenceView";
import IlapPanel from "@/components/crossover/IlapPanel";
import EmptyState from "@/components/shared/EmptyState";
import { GitCompareArrows, Download, Search, AlertTriangle } from "lucide-react";

export default function FederationCrossoverWorkspace() {
  const cx = useCrossover();
  const { isLoading, isError, filtered, crossovers, ilapNodes, summary, matrix, municipalities, agencies, vendorsList, filters, setFilters, resetFilters } = cx;

  return (
    <div>
      <PageHeader
        icon={GitCompareArrows}
        title="Federation Crossover Workspace"
        description="Every area where two or more Federation modules overlap by location, entity, source, contract, agency, vendor, POI, case, airspace event, infrastructure asset, anomaly, or graph relationship. Explicit links take priority; inferred matches are candidates until review-verified. Correlation ≠ causation; UAP analysis is limited to pattern convergence."
        actions={
          <Button variant="outline" size="sm" onClick={() => exportCrossoversCsv(filtered)} disabled={!filtered.length}>
            <Download className="h-4 w-4 mr-2" /> Export CSV
          </Button>
        }
      />

      {isError ? (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-6 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-destructive">Could not load all crossover ledgers</p>
            <p className="text-xs text-muted-foreground mt-1">One or more contributing entities failed to load, so the crossover view may be incomplete. Reload the page; if it persists, check entity access.</p>
          </div>
        </div>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground p-6 text-center">Computing crossovers…</p>
      ) : (
        <div className="space-y-6">
          <CrossoverSummary summary={summary} />

          <div className="rounded-xl border border-border bg-card/50 p-3">
            <CrossoverFilters filters={filters} setFilters={setFilters} resetFilters={resetFilters} municipalities={municipalities} agencies={agencies} vendorsList={vendorsList} />
          </div>

          <Tabs defaultValue="matrix">
            <TabsList>
              <TabsTrigger value="matrix">Matrix</TabsTrigger>
              <TabsTrigger value="pairs">Pairwise Panels</TabsTrigger>
              <TabsTrigger value="convergence">3+ Module Convergence ({summary.multiModule})</TabsTrigger>
              <TabsTrigger value="ilap">ILAP / POIs ({ilapNodes.length})</TabsTrigger>
              <TabsTrigger value="all">All Crossovers ({filtered.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="matrix" className="mt-4">
              <CrossoverMatrix matrix={matrix} onSelectPair={(key) => setFilters((f) => ({ ...f, pair: key }))} />
              <p className="text-xs text-muted-foreground mt-2">Click a populated row to filter the “All Crossovers” tab by that pair.</p>
            </TabsContent>

            <TabsContent value="pairs" className="mt-4">
              <PairPanel crossovers={crossovers} />
            </TabsContent>

            <TabsContent value="convergence" className="mt-4">
              <ConvergenceView crossovers={crossovers} />
            </TabsContent>

            <TabsContent value="ilap" className="mt-4">
              <IlapPanel ilapNodes={ilapNodes} />
            </TabsContent>

            <TabsContent value="all" className="mt-4">
              {filtered.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title="No crossovers match these filters"
                  description="Adjust or reset the filters. Pending and contradicted records are kept visible by default so uncertainty stays surfaced."
                />
              ) : (
                <div className="grid md:grid-cols-2 gap-3">
                  {filtered.map((c) => <CrossoverCard key={c.crossover_id} c={c} />)}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}