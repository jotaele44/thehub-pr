import React, { useState } from "react";
import { federation } from "@/api/federationClient";
import PageHeader from "@/components/shared/PageHeader";
import EmptyState from "@/components/shared/EmptyState";
import IssueRow from "@/components/github/IssueRow";
import NewIssueDialog from "@/components/github/NewIssueDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Github, RefreshCw, Plus, Loader2, AlertCircle } from "lucide-react";
import { MODULES, HUB_REPO } from "@/lib/federation";
import { toast } from "sonner";

const REPOS = [
  { name: "INTSYS-PR", repo: HUB_REPO },
  ...MODULES.map((m) => ({ name: m.name, repo: m.repo_name })),
];

export default function ModuleReadiness() {
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState(REPOS[0].repo);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyNum, setBusyNum] = useState(null);

  const call = (payload) => federation.functions.invoke("githubModuleReadiness", payload);

  const load = async () => {
    if (!owner.trim()) { toast.error("Enter the GitHub owner/org first"); return; }
    setLoading(true); setError(null);
    try {
      const res = await call({ action: "list", owner: owner.trim(), repo });
      setData(res.data);
    } catch (e) {
      setError(e?.response?.data?.error || e.message);
      setData(null);
    }
    setLoading(false);
  };

  const createIssue = async ({ title, body }) => {
    setSaving(true);
    try {
      await call({ action: "createIssue", owner: owner.trim(), repo, title, body });
      toast.success("Issue created");
      setDialogOpen(false);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.error || e.message);
    }
    setSaving(false);
  };

  const toggleIssue = async (item) => {
    setBusyNum(item.number);
    try {
      await call({ action: item.state === "open" ? "closeIssue" : "reopenIssue", owner: owner.trim(), repo, issue_number: item.number });
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.error || e.message);
    }
    setBusyNum(null);
  };

  return (
    <div>
      <PageHeader title="Module Readiness" icon={Github}
        description="Track GitHub issues and pull requests across federation repos to gauge each module's readiness."
        actions={data && <Button onClick={() => setDialogOpen(true)}><Plus className="h-4 w-4 mr-2" />New Issue</Button>}
      />

      <div className="rounded-xl border border-border bg-card p-4 mb-5 flex flex-col sm:flex-row sm:items-end gap-3">
        <div className="space-y-1.5 flex-1">
          <Label className="text-xs">GitHub Owner / Org</Label>
          <Input value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="e.g. my-org" className="bg-background border-border" onKeyDown={(e) => e.key === "Enter" && load()} />
        </div>
        <div className="space-y-1.5 w-full sm:w-64">
          <Label className="text-xs">Repository</Label>
          <Select value={repo} onValueChange={setRepo}>
            <SelectTrigger className="bg-background border-border"><SelectValue /></SelectTrigger>
            <SelectContent>
              {REPOS.map((r) => <SelectItem key={r.repo} value={r.repo}>{r.name} <span className="text-muted-foreground">({r.repo})</span></SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={load} disabled={loading} className="shrink-0">
          {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}Load
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300 flex items-center gap-2 mb-5">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {!data && !error && (
        <div className="rounded-xl border border-border bg-card">
          <EmptyState title="Load a repository" description="Enter the owner and pick a repo, then press Load to view issues and pull requests." />
        </div>
      )}

      {data && (
        <Tabs defaultValue="issues">
          <TabsList className="mb-4">
            <TabsTrigger value="issues">Issues ({data.issues.length})</TabsTrigger>
            <TabsTrigger value="pulls">Pull Requests ({data.pulls.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="issues">
            <div className="rounded-xl border border-border bg-card overflow-hidden">
              {data.issues.length === 0
                ? <EmptyState title="No issues" description="This repo has no issues yet." />
                : data.issues.map((it) => <IssueRow key={it.number} item={it} isPull={false} onToggle={toggleIssue} busy={busyNum === it.number} />)}
            </div>
          </TabsContent>
          <TabsContent value="pulls">
            <div className="rounded-xl border border-border bg-card overflow-hidden">
              {data.pulls.length === 0
                ? <EmptyState title="No pull requests" description="This repo has no pull requests yet." />
                : data.pulls.map((it) => <IssueRow key={it.number} item={it} isPull onToggle={toggleIssue} busy={false} />)}
            </div>
          </TabsContent>
        </Tabs>
      )}

      <NewIssueDialog open={dialogOpen} onOpenChange={setDialogOpen} onCreate={createIssue} saving={saving} />
    </div>
  );
}