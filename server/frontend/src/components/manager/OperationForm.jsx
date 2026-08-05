import React from "react";
import { FileUp, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

// A form generated from an operation's typed parameter schema.
//
// The fields are derived from the signed policy rather than hand-written per
// operation, so the form cannot drift from what the executor will accept. A
// parameter the policy marks `fixed` is not rendered at all: it is not the
// operator's to choose, and showing a disabled input would imply otherwise.
//
// File parameters render a *slot*, not an <input type="file">. The browser
// never learns a filesystem path; the native picker returns an opaque token.
export default function OperationForm({
  fields,
  values,
  onChange,
  tokenSlots = [],
  tokens = {},
  onPickFile,
  disabled = false,
}) {
  if (!fields.length && !tokenSlots.length) {
    return (
      <p className="text-xs text-muted-foreground">
        This operation takes no operator-supplied parameters.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {tokenSlots.map((slot) => (
        <div key={slot.name} className="space-y-1.5 sm:col-span-2">
          {/* A plain heading rather than a <label for>: associating a label
              with the button would replace its accessible name ("Choose
              file…") with the field name, so a screen-reader user would hear
              the parameter twice and never hear the action. */}
          <p className="text-sm font-medium capitalize" id={`slot-label-${slot.name}`}>
            {slot.name.replace(/_/g, " ")}
            <span className="text-status-danger-fg ml-0.5">*</span>
          </p>
          <div className="flex items-center gap-2">
            <Button
              id={`slot-${slot.name}`}
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              aria-describedby={`slot-label-${slot.name}`}
              onClick={() => onPickFile?.(slot)}
            >
              <FileUp className="h-3.5 w-3.5 mr-1.5" />
              {tokens[slot.name] ? "Choose a different file" : "Choose file…"}
            </Button>
            <span className="text-xs text-muted-foreground" data-testid={`token-${slot.name}`}>
              {tokens[slot.name] ? "File selected" : "No file selected"}
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground flex items-center gap-1">
            <Lock className="h-3 w-3" />
            Opened through the native picker. The page never receives the file path.
            {slot.extensions?.length ? ` Accepts ${slot.extensions.join(", ")}.` : ""}
          </p>
        </div>
      ))}

      {fields.map((field) => {
        const id = `param-${field.name}`;
        const common = {
          id,
          disabled,
          "aria-required": field.required || undefined,
        };

        if (field.type === "boolean") {
          return (
            <div key={field.name} className="flex items-center justify-between gap-3 sm:col-span-1">
              <Label htmlFor={id} className="capitalize">
                {field.label}
              </Label>
              <Switch
                {...common}
                checked={Boolean(values[field.name])}
                onCheckedChange={(checked) => onChange(field.name, checked)}
              />
            </div>
          );
        }

        if (field.type === "enum") {
          return (
            <div key={field.name} className="space-y-1.5">
              <Label htmlFor={id} className="capitalize">
                {field.label}
                {field.required && <span className="text-status-danger-fg ml-0.5">*</span>}
              </Label>
              <select
                {...common}
                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                value={values[field.name] ?? ""}
                onChange={(event) => onChange(field.name, event.target.value)}
              >
                <option value="">Select…</option>
                {field.values.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
          );
        }

        const inputType =
          field.type === "integer" || field.type === "number"
            ? "number"
            : field.type === "datetime"
              ? "text"
              : "text";

        return (
          <div key={field.name} className="space-y-1.5">
            <Label htmlFor={id} className="capitalize">
              {field.label}
              {field.required && <span className="text-status-danger-fg ml-0.5">*</span>}
            </Label>
            <Input
              {...common}
              type={inputType}
              value={values[field.name] ?? ""}
              min={field.minimum}
              max={field.maximum}
              placeholder={
                field.type === "datetime"
                  ? "2026-07-27T00:00:00Z"
                  : field.defaultValue !== undefined
                    ? String(field.defaultValue)
                    : ""
              }
              onChange={(event) => onChange(field.name, event.target.value)}
            />
            {(field.type === "directory" ||
              field.type === "managed_file" ||
              field.type === "managed_output_directory" ||
              field.type === "managed_sqlite_path") && (
              <p className="text-[11px] text-muted-foreground">
                Relative to a managed root. Absolute paths and parent traversal are rejected.
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
