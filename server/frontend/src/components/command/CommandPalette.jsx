import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'lucide-react';
import { cn } from '@/lib/utils';
import { buildCommands } from '@/lib/commands';
import useGlobalShortcut from '@/hooks/useGlobalShortcut';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';

const CommandPaletteContext = createContext({ open: () => {} });

export function useCommandPalette() {
  return useContext(CommandPaletteContext);
}

// Global command palette (FDX-055 / TWIN-095): Ctrl/Cmd+K anywhere, or the
// sidebar trigger. A combobox over a listbox: arrows move, Enter runs, Escape
// closes (Radix Dialog traps focus and restores it on close).
export function CommandPalette({ open, onOpenChange }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const commands = useMemo(() => buildCommands(query), [query]);

  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => { if (!open) setQuery(''); }, [open]);

  const run = (command) => {
    if (!command) return;
    onOpenChange(false);
    navigate(command.href);
  };

  const onKeyDown = (event) => {
    const count = commands.length;
    if (event.key === 'ArrowDown' && count) {
      event.preventDefault();
      setActive((index) => (index + 1) % count);
    } else if (event.key === 'ArrowUp' && count) {
      event.preventDefault();
      setActive((index) => (index - 1 + count) % count);
    } else if (event.key === 'Home' && count) {
      event.preventDefault();
      setActive(0);
    } else if (event.key === 'End' && count) {
      event.preventDefault();
      setActive(count - 1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      run(commands[active]);
    }
  };

  const activeId = commands[active] ? `command-option-${active}` : undefined;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl gap-0 p-0" data-command-palette>
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">
          Type to filter destinations, search the Federation, open a record such as Entities/ent_123, or jump the map to coordinates such as 18.2, -66.5.
        </DialogDescription>
        <div className="border-b border-border p-3 pr-12">
          <input
            autoFocus
            role="combobox"
            aria-expanded={commands.length > 0}
            aria-controls="command-palette-list"
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            aria-label="Command, search or record"
            placeholder="Search the Federation, go to a page, or paste lat, lon…"
            className="h-11 w-full rounded-md bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>
        {commands.length ? (
          <ul id="command-palette-list" role="listbox" aria-label="Commands" className="max-h-80 overflow-y-auto p-2">
            {commands.map((command, index) => (
              <li
                key={command.id}
                id={`command-option-${index}`}
                role="option"
                aria-selected={index === active}
                data-command={command.id}
                className={cn(
                  'flex min-h-11 cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-2 text-sm',
                  index === active ? 'bg-accent text-accent-foreground' : 'text-foreground',
                )}
                onMouseEnter={() => setActive(index)}
                onClick={() => run(command)}
              >
                <span className="truncate">{command.label}</span>
                <span className="shrink-0 text-[11px] text-muted-foreground">{command.group}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p role="status" className="p-4 text-sm text-muted-foreground">No command matches “{query}”.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function CommandPaletteProvider({ children }) {
  const [open, setOpen] = useState(false);
  const toggle = useCallback(() => setOpen((value) => !value), []);
  useGlobalShortcut(toggle);
  const value = useMemo(() => ({ open: () => setOpen(true) }), []);
  return (
    <CommandPaletteContext.Provider value={value}>
      {children}
      <CommandPalette open={open} onOpenChange={setOpen} />
    </CommandPaletteContext.Provider>
  );
}

export function CommandPaletteTrigger({ className }) {
  const { open } = useCommandPalette();
  return (
    <button
      type="button"
      onClick={open}
      aria-keyshortcuts="Control+K Meta+K"
      className={cn(
        'flex min-h-10 w-full items-center gap-2 rounded-lg border border-sidebar-border px-3 py-2 text-left text-sm text-sidebar-foreground hover:bg-sidebar-accent/50',
        className,
      )}
    >
      <Command className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="flex-1 truncate">Search &amp; commands</span>
      <kbd className="rounded border border-sidebar-border px-1.5 text-[10px]">Ctrl K</kbd>
    </button>
  );
}
