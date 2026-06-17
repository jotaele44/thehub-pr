import React, { useEffect, useRef, useState } from "react";
import { federation } from "@/api/federationClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import MemoryPanel from "@/components/research/MemoryPanel";
import { Loader2, Send, Trash2, Globe, MessageSquare, Brain } from "lucide-react";

// Per-module (per-child) LLM chat session. Each module keeps its own
// independent, persisted conversation scoped to module + current analyst.
export default function ModuleChat({ module, scopeLine, webGrounded, langInstruction = "" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [me, setMe] = useState(null);
  const [memory, setMemory] = useState(null);
  const [showMemory, setShowMemory] = useState(false);
  const [distilling, setDistilling] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    let active = true;
    (async () => {
      const user = await federation.auth.me().catch(() => null);
      if (active) setMe(user);
      const [rows, mem] = await Promise.all([
        federation.entities.ResearchChat.filter({ module, session_owner: user?.email || "" }, "created_date").catch(() => []),
        federation.entities.ResearchMemory.filter({ module, session_owner: user?.email || "" }, "-distilled_at", 1).catch(() => []),
      ]);
      if (active) {
        setMessages(rows || []);
        setMemory((mem || [])[0] || null);
      }
    })();
    return () => { active = false; };
  }, [module]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);

    const userMsg = await federation.entities.ResearchChat.create({
      module, role: "user", content: text, session_owner: me?.email || "",
    });
    setMessages((m) => [...m, userMsg]);

    const history = [...messages, userMsg]
      .map((x) => `${x.role === "user" ? "Analyst" : "Assistant"}: ${x.content}`)
      .join("\n\n");

    const prompt = `You are the dedicated research assistant for ${scopeLine}, part of the INTSYS-PR investigative federation focused on Puerto Rico. Maintain context across this conversation.

Rules:
- Present results strictly as analytical LEADS / CANDIDATES requiring review — never as proven conclusions.
- When citing evidence, note the tier: T1 Technical, T2 Operational, T3 Eyewitness, T4 Secondary.
- Be neutral; avoid speculative claims. Include source URLs when web sources are used.

Conversation so far:
${history}

Reply to the analyst's latest message.

LANGUAGE: ${langInstruction}`;

    const res = await federation.integrations.Core.InvokeLLM({
      prompt,
      add_context_from_internet: !!webGrounded,
      ...(webGrounded ? { model: "gemini_3_flash" } : {}),
    }).catch((e) => `Error: ${e.message || "request failed"}`);

    const assistantMsg = await federation.entities.ResearchChat.create({
      module, role: "assistant", content: String(res), session_owner: me?.email || "", web_grounded: !!webGrounded,
    });
    setMessages((m) => [...m, assistantMsg]);
    setLoading(false);
  };

  const clearSession = async () => {
    await Promise.all(messages.map((x) => federation.entities.ResearchChat.delete(x.id)));
    setMessages([]);
  };

  // Distill the full transcript into clean, organized key information,
  // stripping filler and keeping only durable, review-ready leads.
  const distillMemory = async () => {
    if (distilling || messages.length === 0) return;
    setShowMemory(true);
    setDistilling(true);

    const transcript = messages
      .map((x) => `${x.role === "user" ? "Analyst" : "Assistant"}: ${x.content}`)
      .join("\n\n");

    const prompt = `You are the memory curator for ${scopeLine}, part of the INTSYS-PR investigative federation focused on Puerto Rico.

Distill the conversation transcript below into clean, organized IMPORTANT INFORMATION. Remove all conversational filler, greetings, hedging, restated questions, and duplication. Keep only durable, review-ready substance.

Output concise markdown with these sections (omit any that are empty):
- **Key Leads / Candidates** — bulleted, each phrased as a lead requiring review (never a conclusion)
- **Entities** — people, agencies, vendors, assets, locations, flights mentioned
- **Evidence & Sources** — note evidence tier (T1 Technical, T2 Operational, T3 Eyewitness, T4 Secondary) and include source URLs when present
- **Open Questions / Next Actions**

Be neutral and avoid speculative claims. Do not invent facts not present in the transcript.

LANGUAGE: ${langInstruction}

Transcript:
${transcript}`;

    const res = await federation.integrations.Core.InvokeLLM({ prompt }).catch((e) => `Error: ${e.message || "request failed"}`);

    const payload = {
      module,
      session_owner: me?.email || "",
      content: String(res),
      message_count: messages.length,
      distilled_at: new Date().toISOString(),
    };

    const saved = memory?.id
      ? await federation.entities.ResearchMemory.update(memory.id, payload)
      : await federation.entities.ResearchMemory.create(payload);
    setMemory(saved);
    setDistilling(false);
  };

  return (
    <Card className="flex flex-col h-[60vh]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {webGrounded ? <Globe className="h-3.5 w-3.5 text-blue-300" /> : <MessageSquare className="h-3.5 w-3.5" />}
          <span>{webGrounded ? "Web-grounded session" : "Session"} · {module}</span>
        </div>
        <div className="flex items-center gap-1">
          {(messages.length > 0 || memory) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowMemory((s) => !s)}
              className={cn("h-7 text-xs", showMemory ? "text-blue-200" : "text-muted-foreground")}
            >
              <Brain className="h-3.5 w-3.5" /> Memory
            </Button>
          )}
          {messages.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearSession} className="h-7 text-xs text-muted-foreground">
              <Trash2 className="h-3.5 w-3.5" /> Clear
            </Button>
          )}
        </div>
      </div>

      {showMemory && (
        <div className="px-4 pt-3">
          <MemoryPanel
            memory={memory}
            distilling={distilling}
            onRegenerate={distillMemory}
            onClose={() => setShowMemory(false)}
            disabled={messages.length === 0}
          />
        </div>
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && !loading && (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
            Start the {module} research session.
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn(
              "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
              m.role === "user" ? "bg-secondary text-secondary-foreground" : "bg-card border border-border"
            )}>
              {m.role === "user" ? (
                <p className="leading-relaxed whitespace-pre-wrap">{m.content}</p>
              ) : (
                <ReactMarkdown className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_a]:text-blue-300">
                  {m.content}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-2.5 bg-card border border-border text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-border p-3 flex items-end gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={`Message the ${module} assistant…`}
          className="min-h-11 max-h-32 resize-none"
        />
        <Button onClick={send} disabled={loading || !input.trim()} size="icon" className="shrink-0">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </Card>
  );
}