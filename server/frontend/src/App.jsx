import { lazy, Suspense } from 'react';
import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Route, Routes, Navigate, Outlet } from 'react-router-dom';
import PageNotFound from './lib/PageNotFound';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import { ThemeProvider } from '@/lib/theme';
import { appParams } from '@/lib/app-params';
import ProtectedRoute from '@/components/ProtectedRoute';
import ScrollToTop from './components/ScrollToTop';
import AppLayout from '@/components/layout/AppLayout';
import RouteFallback from '@/components/shared/RouteFallback';

const Login = lazy(() => import('@/pages/Login'));
const Register = lazy(() => import('@/pages/Register'));
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword'));
const ResetPassword = lazy(() => import('@/pages/ResetPassword'));
const Programs = lazy(() => import('@/pages/Programs'));
const Cases = lazy(() => import('@/pages/Cases'));
const Sources = lazy(() => import('@/pages/Sources'));
const Tasks = lazy(() => import('@/pages/Tasks'));
const Gates = lazy(() => import('@/pages/Gates'));
const Integrations = lazy(() => import('@/pages/Integrations'));
const ExportsPage = lazy(() => import('@/pages/Exports'));
const Manifest = lazy(() => import('@/pages/Manifest'));
const Spiderweb = lazy(() => import('@/pages/Spiderweb'));
const Ovnis = lazy(() => import('@/pages/Ovnis'));
const AguaYLuz = lazy(() => import('@/pages/AguaYLuz'));
const MoneySweep = lazy(() => import('@/pages/MoneySweep'));
const Skywatcher = lazy(() => import('@/pages/Skywatcher'));
const Centinelas = lazy(() => import('@/pages/Centinelas'));
const ModuleReadiness = lazy(() => import('@/pages/ModuleReadiness'));
const TransitionAudit = lazy(() => import('@/pages/TransitionAudit'));
const FederationCrossoverWorkspace = lazy(() => import('@/pages/FederationCrossoverWorkspace'));
const AnomalyOverlap = lazy(() => import('@/pages/AnomalyOverlap'));
const ControlLedgers = lazy(() => import('@/pages/ControlLedgers'));
const Hub = lazy(() => import('@/pages/Hub'));
const RecentActivity = lazy(() => import('@/pages/RecentActivity'));
const ResearchAssistant = lazy(() => import('@/pages/ResearchAssistant'));
const Dictionary = lazy(() => import('@/pages/Dictionary'));
const FederalRecords = lazy(() => import('@/pages/FederalRecords'));

const AppRoutes = () => {
  const { isLoadingPublicSettings, appPublicSettings } = useAuth();

  if (isLoadingPublicSettings) {
    return <RouteFallback />;
  }

  const authRequired = Boolean(
    appPublicSettings?.public_settings?.requires_auth || appParams.requireAuth
  );

  const guard = authRequired
    ? <ProtectedRoute fallback={<RouteFallback />} unauthenticatedElement={<Navigate to="/login" replace />} />
    : <Outlet />;

  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {authRequired ? (
          <>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
          </>
        ) : (
          <>
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/register" element={<Navigate to="/" replace />} />
            <Route path="/forgot-password" element={<Navigate to="/" replace />} />
            <Route path="/reset-password" element={<Navigate to="/" replace />} />
          </>
        )}

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
            <Route path="/federal-records" element={<FederalRecords />} />
            <Route path="/federal-records/releases" element={<FederalRecords />} />
            <Route path="/federal-records/findings" element={<FederalRecords />} />
            <Route path="/federal-records/redaction-changes" element={<FederalRecords />} />
            <Route path="/federal-records/corpus-versions" element={<FederalRecords />} />
            <Route path="/cases/:caseId/fedmil-context" element={<FederalRecords />} />
            <Route path="/cases/:caseId/fedmil-context/contradictions" element={<FederalRecords />} />
            <Route path="/cases/:caseId/fedmil-context/data-gaps" element={<FederalRecords />} />
          </Route>
        </Route>

        <Route path="*" element={<PageNotFound />} />
      </Routes>
    </Suspense>
  );
};

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <QueryClientProvider client={queryClientInstance}>
          <Router>
            <ScrollToTop />
            <AppRoutes />
          </Router>
          <Toaster />
        </QueryClientProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
