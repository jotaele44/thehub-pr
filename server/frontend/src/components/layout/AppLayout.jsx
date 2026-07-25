import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import MobileNav from "./MobileNav";
import MobileBottomNav from "./MobileBottomNav";
import NotificationBell from "@/components/notifications/NotificationBell";

export default function AppLayout() {
  return (
    <div className="min-h-screen flex bg-background">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <MobileNav />
        <main id="main-content" tabIndex={-1} className="flex-1 px-4 sm:px-6 lg:px-8 py-6 pb-[calc(5rem+env(safe-area-inset-bottom))] lg:pb-6 max-w-[1600px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
      <div className="fixed top-[calc(0.75rem+env(safe-area-inset-top))] right-3 z-50 lg:top-3">
        <NotificationBell />
      </div>
      <MobileBottomNav />
    </div>
  );
}
