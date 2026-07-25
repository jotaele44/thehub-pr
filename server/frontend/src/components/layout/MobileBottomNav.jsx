import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Activity, Bell, Search, Map, Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { label: "Activity", path: "/", icon: Activity },
  { label: "Alerts", path: "/centinelas", icon: Bell },
  { label: "Search", path: "/research", icon: Search },
  { label: "Map", path: "/spiderweb", icon: Map },
  { label: "More", path: "/programs", icon: Menu },
];

const isActive = (pathname, path) => path === "/" ? pathname === "/" || pathname.startsWith("/activity") : pathname === path || pathname.startsWith(`${path}/`);

export default function MobileBottomNav() {
  const { pathname } = useLocation();
  return (
    <nav aria-label="Mobile primary" className="mobile-bottom-nav md:hidden fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85">
      <div className="grid grid-cols-5">
        {ITEMS.map(({ label, path, icon: Icon }) => {
          const active = isActive(pathname, path);
          return (
            <Link key={path} to={path} aria-current={active ? "page" : undefined} className={cn("min-h-14 flex flex-col items-center justify-center gap-1 px-1 text-[11px] font-medium", active ? "text-foreground" : "text-muted-foreground hover:text-foreground")}>
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span className="truncate max-w-full">{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}