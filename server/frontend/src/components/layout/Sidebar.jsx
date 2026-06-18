import React from "react";
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import { MODULES, domainAccent } from "@/lib/federation";
import {
  Hexagon, Network, Radar, Droplets, Banknote, Plane,
} from "lucide-react";

const MODULE_ICONS = {
  "Spiderweb-PR": Network,
  "Ovnis-PR": Radar,
  "AguaYLuz-PR": Droplets,
  "MoneySweep-PR": Banknote,
  "Skywatcher-PR": Plane,
};

// Hub = 6th module: parent control plane + all federation & crossover surfaces.
const HUB = { name: "Hub", path: "/", domain: "ControlPlane", icon: Hexagon };

function NavItem({ item, active, accentDot }) {
  const Icon = item.icon;
  return (
    <Link
      to={item.path}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
        active ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
      )}
    >
      {accentDot ? (
        <span className={cn("h-2 w-2 rounded-full shrink-0", accentDot)} />
      ) : (
        <Icon className="h-4 w-4 shrink-0" />
      )}
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export default function Sidebar() {
  const { pathname } = useLocation();
  const isActive = (p) => (p === "/" ? pathname === "/" : pathname.startsWith(p));

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

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">Modules</div>
        <NavItem
          item={{ label: HUB.name, path: HUB.path, icon: HUB.icon }}
          active={pathname === "/" || pathname.startsWith("/hub")}
          accentDot={domainAccent(HUB.domain).dot}
        />
        {MODULES.map((m) => {
          const accent = domainAccent(m.domain);
          return (
            <NavItem
              key={m.path}
              item={{ label: m.name, path: m.path, icon: MODULE_ICONS[m.name] }}
              active={isActive(m.path)}
              accentDot={accent.dot}
            />
          );
        })}
      </nav>

      <div className="px-5 py-3 border-t border-sidebar-border text-[10px] text-sidebar-foreground/50">
        Sanitized metadata only · Gated sync
      </div>
    </aside>
  );
}