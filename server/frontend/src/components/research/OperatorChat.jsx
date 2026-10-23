import React, { useEffect, useRef, useState } from "react";
import { federation, requireImplementedResponse } from "@/api/federationClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import MessageBubble from "@/components/research/MessageBubble";
import { Loader2, Send, Paperclip, X, ShieldCheck, Plus, AlertTriangle } from "lucide-react";

const AGENT = "research_operator";

// Research Operator chat is usable only when the deployment provides an agent
// backend; diagnostic mode reports that external prerequisite instead of faking a session.
export default function OperatorChat() {
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);
  const unsubscribeRef = useRef(null);

  // Create a fresh conversation on mount and subscribe to streamed updates.
  useEffect(() => {
    let unsub;
    let active = true;
    (async () => {
      try {
        const conv = requireImplementedResponse(
          await federation.agents.createConversation({
            agent_name: AGENT,
            metadata: { name: "Research Operator session", description: "INTSYS-PR operator chat" },
          }),
          "Research Operator",
        );
        if (!active) return;
        setConversation(conv);
        setMessages(conv.messages || []);
        unsub = federation.agents.subscribeToConversation(conv.id, (data) => {
          setMessages(data.messages || []);
        });
        unsubscribeRef.current = unsub;
      } catch (err) {
        if (active) setError(err.message || "Research Operator is unavailable.");
      }
    })();
    return () => {
      active = false;
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const startNew = async () => {
    setError(null);
    try {
      const conv = requireImplementedResponse(
        await federation.agents.createConversation({
          agent_name: AGENT,
          metadata: { name: "Research Operator session", description: "INTSYS-PR operator chat" },
        }),
        "Research Operator",
      );
      unsubscribeRef.current?.();
      unsubscribeRef.current = federation.agents.subscribeToConversation(conv.id, (data) => {
        setMessages(data.messages || []);
      });
      setConversation(conv);
      setMessages(conv.messages || []);
    } catch (err) {
      setError(err.message || "Could not start a Research Operator session.");
    }
  };

  const onPickFiles = async (e) => {
    const picked = Array.from(e.target.files || []);
    if (!picked.length) return;
    setUploading(true);
    setError(null);
    try {
      const uploaded = [];
      for (const file of picked) {
        const response = requireImplementedResponse(
          await federation.integrations.Core.UploadFile({ file }),
          "File uploads",
        );
        if (!response?.file_url) {
          throw new Error("The file service did not return a usable file URL.");
        }
        uploaded.push({ name: file.name, url: response.file_url });
      }
      setFiles((f) => [...f, ...uploaded]);
      e.target.value = "";
    } catch (err) {
      setError(err.message || "Could not attach the selected files.");
    } finally {
      setUploading(false);
    }
  };

  const send = async () => {
    const text = input.trim();
    if ((!text && files.length === 0) || sending || !conversation) return;
    setSending(true);
    setError(null);
    try {
      requireImplementedResponse(
        await federation.agents.addMessage(conversation, {
          role: "user",
          content: text || "(see attached files)",
          ...(files.length ? { file_urls: files.map((f) => f.url) } : {}),
        }),
        "Research Operator",
      );
      setInput("");
      setFiles([]);
    } catch (err) {
      setError(err.message || "Could not send the message.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Card className="flex flex-col h-[60vh]">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {conversation
            ? <ShieldCheck className="h-3.5 w-3.5 text-status-success-fg" />
            : <AlertTriangle className="h-3.5 w-3.5 text-status-danger-fg" />}
          <span>
            {conversation
              ? "Research Operator · governed actions, file & Drive reads"
              : "Research Operator · agent backend required"}
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={startNew} className="h-7 text-xs text-muted-foreground">
          <Plus className="h-3.5 w-3.5" /> New session
        </Button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {error && (
          <div role="alert" className="rounded-md border border-status-danger/30 bg-status-danger/5 px-3 py-2 text-sm text-status-danger-fg">
            {error}
          </div>
        )}
        {messages.length === 0 && !sending && conversation && (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground text-center px-6">
            Ask the operator to research a lead, read an attached file, search your Google Drive, or log/promote cases, sources, tasks and gates under federation governance.
          </div>
        )}
        {messages.map((m, i) => <MessageBubble key={m.id || i} message={m} />)}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-2.5 bg-card border border-border text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Working…
            </div>
          </div>
        )}
      </div>

      {files.length > 0 && (
        <div className="px-3 pt-2 flex flex-wrap gap-1.5">
          {files.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary/50 px-2 py-0.5 text-xs">
              <Paperclip className="h-3 w-3 text-muted-foreground" />
              <span className="max-w-[12rem] truncate">{f.name}</span>
              <button onClick={() => setFiles((arr) => arr.filter((_, idx) => idx !== i))}>
                <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="border-t border-border p-3 flex items-end gap-2">
        <input ref={fileInputRef} type="file" multiple className="hidden" onChange={onPickFiles} />
        <Button
          variant="outline"
          size="icon"
          className="shrink-0"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading || !conversation}
          title="Attach files for the operator to read"
        >
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
        </Button>
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Message the Research Operator…"
          className="min-h-11 max-h-32 resize-none"
          disabled={!conversation}
        />
        <Button onClick={send} disabled={!conversation || sending || (!input.trim() && files.length === 0)} size="icon" className="shrink-0">
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
    </Card>
  );
}