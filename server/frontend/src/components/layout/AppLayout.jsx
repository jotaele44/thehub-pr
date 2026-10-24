import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import HubHeader from "../../zip-design/HubHeader";
import MobileNav from "./MobileNav";
import NotificationBell from "@/components/notifications/NotificationBell";
import { CommandPaletteProvider } from "@/components/command/CommandPalette";

export default function AppLayout() {
  return (
    <CommandPaletteProvider>
      <div className="zip-surface min-h-screen flex bg-background">
        <Sidebar />
        <div className="flex-1 min-w-0 flex flex-col">
          <HubHeader />
        <div data-offline-status-host style={{ padding: "2px 12px", flexShrink: 0 }} />
          <MobileNav />
          <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 max-w-[1600px] w-full mx-auto">
            <Outlet />
          </main>
        </div>
        {/* Fixed overlay so the notification center is reachable on every page
            without reflowing page content (keeps the layout geometry stable). */}
        <div className="fixed top-3 right-3 z-50">
          <NotificationBell />
        </div>
      </div>
    </CommandPaletteProvider>
  );
}
