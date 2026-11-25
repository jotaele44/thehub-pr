import React from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { FederationAppShell } from "@pr-federation/react";
import NotificationBell from "@/components/notifications/NotificationBell";
import ThemeToggle from "@/components/shared/ThemeToggle";
import { CommandPaletteProvider, CommandPaletteTrigger } from "@/components/command/CommandPalette";
import { NAV_GROUPS } from "@/lib/nav";

// The shared shell does not know about the router: it is told the current
// path and draws each entry through this.
function renderLink({ item, active, href, ...anchor }) {
  return <Link to={href} {...anchor} />;
}

// The Hub's layout is the federation shell (docs/FEDERATION_GUI_STANDARD.md
// §4) with the Hub's content in its slots. Navigation, the skip link, the
// current-page marker and the small-screen bottom bar all come from the shell;
// a page is added to the navigation in lib/nav.js and nowhere else.
export default function AppLayout() {
  const { pathname } = useLocation();
  return (
    <CommandPaletteProvider>
      <FederationAppShell
        nav={NAV_GROUPS}
        current={pathname}
        renderLink={renderLink}
        focusMainOnNavigate
        header={(
          <>
            <div className="min-w-0 leading-tight">
              <p className="truncate text-sm font-semibold tracking-wide">TheHub</p>
              <p className="truncate text-[11px] uppercase tracking-wider text-muted-foreground">
                PRII federation control plane
              </p>
            </div>
            <div className="ml-auto flex shrink-0 items-center gap-1">
              <NotificationBell />
              <ThemeToggle />
            </div>
          </>
        )}
        navHeader={<CommandPaletteTrigger />}
        navFooter={(
          <p className="text-[11px] leading-snug text-muted-foreground">
            Sanitized metadata only · Gated sync
          </p>
        )}
      >
        <div className="mx-auto w-full max-w-[1600px] sm:px-2 lg:px-4 sm:py-2">
          <Outlet />
        </div>
      </FederationAppShell>
    </CommandPaletteProvider>
  );
}
