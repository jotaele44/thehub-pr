import React from "react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { NAV_GROUPS, isNavActive } from "@/lib/nav";

function NavItem({ item, active }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.path}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
        active ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
      )}
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
}

export default function Sidebar() {
  const { pathname } = useLocation();

  return (
    <aside className="hidden lg:flex flex-col w-64 shrink-0 bg-sidebar border-r border-sidebar-border h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-sidebar-border">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center font-semibold text-sm">PR</div>
          <div>
            <div className="text-sm font-semibold text-sidebar-accent-foreground tracking-tight">INTSYS-PR</div>
            <div className="text-[10px] text-sidebar-foreground uppercase tracking-widest">Control Plane</div>
          </div>
        </div>
      </div>

      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="space-y-1">
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">{group.label}</div>
            {group.items.map((item) => (
              <NavItem key={item.path} item={item} active={isNavActive(pathname, item.path)} />
            ))}
          </div>
        ))}
      </nav>

      <div className="px-5 py-3 border-t border-sidebar-border text-[10px] text-sidebar-foreground/50">
        Sanitized metadata only · Gated sync
      </div>
    </aside>
  );
}
