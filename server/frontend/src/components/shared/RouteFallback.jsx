import React from "react";

// Full-screen loading state shown while a lazily-loaded route chunk (or the
// initial auth check) resolves. Shared by App's Suspense boundary and the
// auth-loading / ProtectedRoute fallbacks so the spinner is defined once.
export default function RouteFallback() {
  return (
    <div className="fixed inset-0 flex items-center justify-center" role="status" aria-label="Loading">
      <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
    </div>
  );
}
