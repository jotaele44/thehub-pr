import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

export default function NewIssueDialog({ open, onOpenChange, onCreate, saving }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const submit = () => {
    onCreate({ title, body });
  };

  useEffect(() => {
    if (open) { setTitle(""); setBody(""); }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border">
        <DialogHeader><DialogTitle>New Readiness Issue</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1.5">
            <Label className="text-xs">Title</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Verify schema review gate" className="bg-background border-border" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Description</Label>
            <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Readiness criteria…" className="bg-background border-border min-h-[100px]" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
          <Button onClick={submit} disabled={saving || !title.trim()}>
            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Create Issue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}