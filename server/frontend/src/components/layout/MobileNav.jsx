import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { MODULES, domainAccent } from "@/lib/federation";

const HUB = { name: "Hub", path: "/", domain: "ControlPlane" };

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const isActive = (p) => (p === "/" ? pathname === "/" : pathname.startsWith(p));

  return (
    <div className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-sidebar sticky top-0 z-40">
      <div className="flex items-center gap-2">
        <div className="h-7 w-7 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-semibold text-xs">PR</div>
        <span className="text-sm font-semibold tracking-tight">INTSYS-PR</span>
      </div>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon"><Menu className="h-5 w-5" /></Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 bg-sidebar border-sidebar-border p-0">
          <nav className="px-3 py-5 space-y-1 overflow-y-auto h-full">
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">Modules</div>
            <Link to={HUB.path} onClick={() => setOpen(false)}
              className={cn("flex items-center gap-2 px-3 py-2 rounded-lg text-sm", (pathname === "/" || pathname.startsWith("/hub")) ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-sidebar-foreground")}>
              <span className={cn("h-2 w-2 rounded-full", domainAccent(HUB.domain).dot)} />
              {HUB.name}
            </Link>
            {MODULES.map((m) => (
              <Link key={m.path} to={m.path} onClick={() => setOpen(false)}
                className={cn("flex items-center gap-2 px-3 py-2 rounded-lg text-sm", isActive(m.path) ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-sidebar-foreground")}>
                <span className={cn("h-2 w-2 rounded-full", domainAccent(m.domain).dot)} />
                {m.name}
              </Link>
            ))}
          </nav>
        </SheetContent>
      </Sheet>
    </div>
  );
}