import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes, Navigate, Outlet } from 'react-router-dom';
import PageNotFound from './lib/PageNotFound';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import { appParams } from '@/lib/app-params';
import ProtectedRoute from '@/components/ProtectedRoute';
import ScrollToTop from './components/ScrollToTop';
import AppLayout from '@/components/layout/AppLayout';
import Login from '@/pages/Login';
import Register from '@/pages/Register';
import ForgotPassword from '@/pages/ForgotPassword';
import ResetPassword from '@/pages/ResetPassword';
import Programs from '@/pages/Programs';
import Cases from '@/pages/Cases';
import Sources from '@/pages/Sources';
import Tasks from '@/pages/Tasks';
import Gates from '@/pages/Gates';
import Integrations from '@/pages/Integrations';
import ExportsPage from '@/pages/Exports';
import Manifest from '@/pages/Manifest';
import Spiderweb from '@/pages/Spiderweb';
import Ovnis from '@/pages/Ovnis';
import AguaYLuz from '@/pages/AguaYLuz';
import MoneySweep from '@/pages/MoneySweep';
import Skywatcher from '@/pages/Skywatcher';
import Centinelas from '@/pages/Centinelas';
import ModuleReadiness from '@/pages/ModuleReadiness';
import TransitionAudit from '@/pages/TransitionAudit';
import FederationCrossoverWorkspace from '@/pages/FederationCrossoverWorkspace';
import AnomalyOverlap from '@/pages/AnomalyOverlap';
import ControlLedgers from '@/pages/ControlLedgers';
import Hub from '@/pages/Hub';
import RecentActivity from '@/pages/RecentActivity';
import ResearchAssistant from '@/pages/ResearchAssistant';
import Dictionary from '@/pages/Dictionary';

const FullScreenSpinner = () => (
  <div className="fixed inset-0 flex items-center justify-center" role="status" aria-label="Loading">
    <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
  </div>
);

const AppRoutes = () => {
  const { isLoadingPublicSettings, appPublicSettings } = useAuth();

  // Wait for public settings before routing — we need to know whether auth is
  // required before deciding whether to guard the app routes or render anonymously.
  if (isLoadingPublicSettings) {
    return <FullScreenSpinner />;
  }

  const authRequired = Boolean(
    appPublicSettings?.public_settings?.requires_auth || appParams.requireAuth
  );

  // When auth is required, wrap the app shell in ProtectedRoute (redirects
  // unauthenticated users to /login). In public/diagnostic mode the layout route
  // is a pass-through so the app renders anonymously.
  const guard = authRequired
    ? <ProtectedRoute fallback={<FullScreenSpinner />} unauthenticatedElement={<Navigate to="/login" replace />} />
    : <Outlet />;

  return (
    <Routes>
      {/* Public auth routes — rendered without the app shell. */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* Protected application. */}
      <Route element={guard}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<RecentActivity />} />
          <Route path="/activity" element={<RecentActivity />} />
          <Route path="/programs" element={<Programs />} />
          <Route path="/cases" element={<Cases />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/gates" element={<Gates />} />
          <Route path="/integrations" element={<Integrations />} />
          <Route path="/exports" element={<ExportsPage />} />
          <Route path="/readiness" element={<ModuleReadiness />} />
          <Route path="/transition" element={<TransitionAudit />} />
          <Route path="/crossover" element={<FederationCrossoverWorkspace />} />
          <Route path="/anomaly-overlap" element={<AnomalyOverlap />} />
          <Route path="/control" element={<ControlLedgers />} />
          <Route path="/hub" element={<Hub />} />
          <Route path="/research" element={<ResearchAssistant />} />
          <Route path="/dictionary" element={<Dictionary />} />
          <Route path="/manifest" element={<Manifest />} />
          <Route path="/spiderweb" element={<Spiderweb />} />
          <Route path="/ovnis" element={<Ovnis />} />
          <Route path="/aguayluz" element={<AguaYLuz />} />
          <Route path="/moneysweep" element={<MoneySweep />} />
          <Route path="/skywatcher" element={<Skywatcher />} />
          <Route path="/centinelas" element={<Centinelas />} />
        </Route>
      </Route>

      <Route path="*" element={<PageNotFound />} />
    </Routes>
  );
};


function App() {

  return (
    <AuthProvider>
      <QueryClientProvider client={queryClientInstance}>
        <Router>
          <ScrollToTop />
          <AppRoutes />
        </Router>
        <Toaster />
      </QueryClientProvider>
    </AuthProvider>
  )
}

export default App
