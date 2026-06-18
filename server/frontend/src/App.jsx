import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter, HashRouter, Route, Routes } from 'react-router-dom';
const Router = import.meta.env.VITE_OFFLINE === '1' ? HashRouter : BrowserRouter;
import PageNotFound from './lib/PageNotFound';
import { AuthProvider, useAuth } from '@/lib/AuthContext';
import UserNotRegisteredError from '@/components/UserNotRegisteredError';
import ScrollToTop from './components/ScrollToTop';
import AppLayout from '@/components/layout/AppLayout';
import Dashboard from '@/pages/Dashboard';
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
import ModuleReadiness from '@/pages/ModuleReadiness';
import TransitionAudit from '@/pages/TransitionAudit';
import FederationCrossoverWorkspace from '@/pages/FederationCrossoverWorkspace';
import AnomalyOverlap from '@/pages/AnomalyOverlap';
import ControlLedgers from '@/pages/ControlLedgers';
import Hub from '@/pages/Hub';
import ResearchAssistant from '@/pages/ResearchAssistant';
import Dictionary from '@/pages/Dictionary';

const AuthenticatedApp = () => {
  const { isLoadingAuth, isLoadingPublicSettings, authError, navigateToLogin } = useAuth();

  // Show loading spinner while checking app public settings or auth
  if (isLoadingPublicSettings || isLoadingAuth) {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-slate-200 border-t-slate-800 rounded-full animate-spin"></div>
      </div>
    );
  }

  // Handle authentication errors
  if (authError) {
    if (authError.type === 'user_not_registered') {
      return <UserNotRegisteredError />;
    } else if (authError.type === 'auth_required') {
      // Redirect to login automatically
      navigateToLogin();
      return null;
    }
  }

  // Render the main app
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Hub />} />
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
          <AuthenticatedApp />
        </Router>
        <Toaster />
      </QueryClientProvider>
    </AuthProvider>
  )
}

export default App