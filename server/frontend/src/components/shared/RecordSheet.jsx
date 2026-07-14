import React, { useState, useEffect } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2 } from "lucide-react";

// fields: [{ key, label, type: 'text'|'textarea'|'select'|'number'|'date', options?, required?, placeholder?, full? }]
export default function RecordSheet({ open, onOpenChange, title, fields, initial, onSave, saving }) {
  const [form, setForm] = useState({});

  useEffect(() => {
    if (open) setForm(initial || {});
  }, [open, initial]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSave = () => {
    const cleaned = { ...form };
    fields.forEach((f) => {
      if (f.type === "number" && cleaned[f.key] !== undefined && cleaned[f.key] !== "") {
        cleaned[f.key] = Number(cleaned[f.key]);
      }
    });
    onSave(cleaned);
  };

  const missingRequired = fields.some((f) => f.required && (form[f.key] === undefined || form[f.key] === ""));

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto bg-card border-border flex flex-col">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
        </SheetHeader>

        <div className="grid grid-cols-2 gap-4 py-4 flex-1">
          {fields.map((f) => (
            <div key={f.key} className={f.full || f.type === "textarea" ? "col-span-2 space-y-1.5" : "space-y-1.5"}>
              <Label className="text-xs">{f.label}{f.required && <span className="text-status-danger-fg"> *</span>}</Label>
              {f.type === "select" ? (
                <Select value={form[f.key] ?? ""} onValueChange={(v) => set(f.key, v)}>
                  <SelectTrigger className="bg-background border-border"><SelectValue placeholder={f.placeholder || "Select…"} /></SelectTrigger>
                  <SelectContent>
                    {f.options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                  </SelectContent>
                </Select>
              ) : f.type === "textarea" ? (
                <Textarea value={form[f.key] ?? ""} onChange={(e) => set(f.key, e.target.value)} placeholder={f.placeholder} className="bg-background border-border min-h-[80px]" />
              ) : (
                <Input
                  type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                  value={form[f.key] ?? ""}
                  onChange={(e) => set(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  className="bg-background border-border"
                />
              )}
            </div>
          ))}
        </div>

        <SheetFooter className="flex-row justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving || missingRequired}>
            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Save
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}