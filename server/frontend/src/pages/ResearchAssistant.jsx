import React, { useState } from "react";
import { federation } from "@/api/federationClient";
import PageHeader from "@/components/shared/PageHeader";
import ResearchFindingCard from "@/components/research/ResearchFindingCard";
import EmptyState from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import ModuleChat from "@/components/research/ModuleChat";
import OperatorChat from "@/components/research/OperatorChat";
import { Sparkles, Loader2, Search, AlertTriangle, Languages } from "lucide-react";

const LANGUAGES = [
  { value: "es", label: "Español", instruction: "Responde en español." },
  { value: "en", label: "English", instruction: "Respond in English." },
  { value: "bilingual", label: "Bilingüe / Bilingual", instruction: "Respond in BOTH Spanish and English: write each section first in Spanish, then immediately in English." },
];

const MODULE_SCOPES = [
  { value: "Any", label: "Any module / general" },
  { value: "Spiderweb-PR", label: "Spiderweb-PR — infrastructure & terrain" },
  { value: "Ovnis-PR", label: "Ovnis-PR — UAP/USO cases" },
  { value: "AguaYLuz-PR", label: "AguaYLuz-PR — water & power" },
  { value: "MoneySweep-PR", label: "MoneySweep-PR — contracts & vendors" },
  { value: "Skywatcher-PR", label: "Skywatcher-PR — aviation" },
];

// Per-child chat sessions: each module (plus the parent Hub) gets its own
// independent, persisted conversation with the LLM.
const CHAT_MODULES = [
  { module: "Hub", label: "Hub", scopeLine: "the INTSYS-PR parent control plane" },
  { module: "Spiderweb-PR", label: "Spiderweb", scopeLine: "the Spiderweb-PR module (infrastructure, terrain, hydro, utility, contractor & geospatial analysis)" },
  { module: "Ovnis-PR", label: "Ovnis", scopeLine: "the Ovnis-PR module (UAP/USO cases, witness reports, sightings)" },
  { module: "AguaYLuz-PR", label: "AguaYLuz", scopeLine: "the AguaYLuz-PR module (water, power, PRASA, LUMA, dams, reservoirs)" },
  { module: "MoneySweep-PR", label: "MoneySweep", scopeLine: "the MoneySweep-PR module (contracts, vendors, awards, agencies, procurement)" },
  { module: "Skywatcher-PR", label: "Skywatcher", scopeLine: "the Skywatcher-PR module (aircraft, flights, ADS-B/FR24, aviation anomalies)" },
];

const RESPONSE_SCHEMA = {
  type: "object",
  properties: {
    overview: { type: "string", description: "Brief neutral overview framed as leads, not conclusions" },
    findings: {
      type: "array",
      items: {
        type: "object",
        properties: {
          headline: { type: "string" },
          summary: { type: "string" },
          municipality: { type: "string" },
          evidence_tier: { type: "string", enum: ["T1", "T2", "T3", "T4"] },
          confidence: { type: "string", enum: ["Low", "Medium", "High"] },
          sources: {
            type: "array",
            items: {
              type: "object",
              properties: { title: { type: "string" }, url: { type: "string" } },
            },
          },
        },
      },
    },
  },
};

export default function ResearchAssistant() {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("Any");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [chatModule, setChatModule] = useState("Hub");
  const [webGrounded, setWebGrounded] = useState(true);
  const [language, setLanguage] = useState("es");

  const langInstruction = LANGUAGES.find((l) => l.value === language)?.instruction || "";

  const run = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const scopeLine = scope === "Any" ? "the Puerto Rico research federation" : `the ${scope} module`;
    const prompt = `You are a research analyst supporting INTSYS-PR, an investigative federation focused on Puerto Rico. Research the following query in the context of ${scopeLine} using current web sources.

QUERY: ${query}

Rules:
- Present results strictly as analytical LEADS / CANDIDATES requiring review — never as proven conclusions.
- For every finding, assign an evidence tier: T1 Technical (sensor/official dataset/instrument), T2 Operational (agency/contractor/procurement/utility/aviation records), T3 Eyewitness (firsthand report), T4 Secondary (news/blog/archive/commentary).
- Assign a confidence (Low/Medium/High) reflecting source quality and corroboration.
- Include real, verifiable source URLs for each finding. Prefer official and primary sources.
- Where applicable, note the Puerto Rico municipality.
- Be neutral and avoid speculative claims.

LANGUAGE: ${langInstruction}`;

    try {
      const res = await federation.integrations.Core.InvokeLLM({
        prompt,
        add_context_from_internet: true,
        model: "gemini_3_flash",
        response_json_schema: RESPONSE_SCHEMA,
      });
      setResult(res);
    } catch (e) {
      setError(e.message || "Research query failed.");
    }
    setLoading(false);
  };

  const findings = result?.findings || [];

  return (
    <div>
      <PageHeader
        title="Research Assistant"
        description="Internet-grounded LLM research. Results are returned as source-backed leads with evidence tiers and confidence — for analyst review, not as conclusions."
        icon={Sparkles}
      />

      <Tabs defaultValue="chat" className="w-full">
        <TabsList className="mb-5">
          <TabsTrigger value="chat">Module Chat Sessions</TabsTrigger>
          <TabsTrigger value="operator">Research Operator</TabsTrigger>
          <TabsTrigger value="query">Structured Research</TabsTrigger>
        </TabsList>

        <TabsContent value="operator">
          <p className="text-sm text-muted-foreground mb-4">
            The Research Operator can research leads, read files you attach, search the connected Google Drive, normalize terms, and log or promote cases, sources, tasks and gates under federation governance.
          </p>
          <OperatorChat />
        </TabsContent>

        <TabsContent value="chat">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <p className="text-sm text-muted-foreground">
              Each module keeps its own independent, persisted conversation with the LLM.
            </p>
            <div className="flex items-center gap-3 shrink-0">
              <div className="flex items-center gap-2">
                <Languages className="h-3.5 w-3.5 text-muted-foreground" />
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger className="h-8 w-40 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LANGUAGES.map((l) => (
                      <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <Switch id="web-grounded" checked={webGrounded} onCheckedChange={setWebGrounded} />
                <Label htmlFor="web-grounded" className="text-xs text-muted-foreground">Web search</Label>
              </div>
            </div>
          </div>
          <Tabs value={chatModule} onValueChange={setChatModule}>
            <TabsList className="mb-4 flex-wrap h-auto">
              {CHAT_MODULES.map((m) => (
                <TabsTrigger key={m.module} value={m.module}>{m.label}</TabsTrigger>
              ))}
            </TabsList>
            {CHAT_MODULES.map((m) => (
              <TabsContent key={m.module} value={m.module}>
                <ModuleChat module={m.module} scopeLine={m.scopeLine} webGrounded={webGrounded} langInstruction={langInstruction} />
              </TabsContent>
            ))}
          </Tabs>
        </TabsContent>

        <TabsContent value="query">
      <Card className="p-4 space-y-3 mb-6">
        <Textarea
          placeholder="Describe what to research, e.g. 'Recent FEMA-funded reservoir repair contracts in Ponce' or 'Documented UAP sightings near Cabo Rojo radar'..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="min-h-24"
        />
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <Select value={scope} onValueChange={setScope}>
            <SelectTrigger className="sm:w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MODULE_SCOPES.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="sm:w-44">
              <Languages className="h-3.5 w-3.5 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LANGUAGES.map((l) => (
                <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={run} disabled={loading || !query.trim()} className="sm:ml-auto">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            {loading ? "Researching…" : "Run Research"}
          </Button>
        </div>
      </Card>

      {error && (
        <Card className="p-4 mb-6 border-red-500/30 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-red-300 mt-0.5 shrink-0" />
          <p className="text-sm text-red-300">{error}</p>
        </Card>
      )}

      {loading && (
        <div className="flex items-center justify-center py-16 text-muted-foreground gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" /> Searching the web and synthesizing leads…
        </div>
      )}

      {result && (
        <div className="space-y-4">
          {result.overview && (
            <Card className="p-4">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70 mb-1">Overview</div>
              <p className="text-sm text-muted-foreground leading-relaxed">{result.overview}</p>
            </Card>
          )}
          {findings.length > 0 ? (
            <div className="grid gap-3">
              {findings.map((f, i) => <ResearchFindingCard key={i} finding={f} index={i} />)}
            </div>
          ) : (
            <EmptyState icon={Search} title="No leads returned" description="Try rephrasing or broadening the query." />
          )}
        </div>
      )}

      {!result && !loading && !error && (
        <EmptyState icon={Sparkles} title="Run a research query" description="Web-grounded findings will appear here with evidence tiers and sources." />
      )}
        </TabsContent>
      </Tabs>
    </div>
  );
}