import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_GROUPS, isNavActive } from "@/lib/nav";
import ThemeToggle from "@/components/shared/ThemeToggle";

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  return (
    <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-sidebar sticky top-0 z-40">
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-semibold text-xs">PR</div>
        <span className="text-sm font-semibold tracking-tight">INTSYS-PR</span>
      </div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Open navigation menu"><Menu className="h-5 w-5" /></Button>
          </SheetTrigger>
        <SheetContent side="left" className="w-72 bg-sidebar border-sidebar-border p-0">
          <nav aria-label="Primary" className="px-3 py-5 space-y-4 overflow-y-auto h-full">
            {NAV_GROUPS.map((group) => (
              <div key={group.label} className="space-y-1">
                <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">{group.label}</div>
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={() => setOpen(false)}
                      className={cn("flex items-center gap-2 px-3 py-2 rounded-lg text-sm", isNavActive(pathname, item.path) ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-sidebar-foreground")}
                    >
                      {item.accentDot ? (
                        <span aria-hidden="true" className={cn("h-2 w-2 rounded-full shrink-0", item.accentDot)} />
                      ) : Icon ? (
                        <Icon className="h-4 w-4 shrink-0" />
                      ) : (
                        <span className="h-4 w-4 shrink-0" />
                      )}
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}
