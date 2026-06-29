import { useLocation, Link } from 'react-router-dom';
import { federation } from '@/api/federationClient';
import { useQuery } from '@tanstack/react-query';

export default function PageNotFound() {
  const location = useLocation();
  const pageName = location.pathname.substring(1);
  const { data: authData, isFetched } = useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      try {
        const user = await federation.auth.me();
        return { user, isAuthenticated: true };
      } catch {
        return { user: null, isAuthenticated: false };
      }
    }
  });

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-950 text-slate-100">
      <div className="max-w-md w-full text-center space-y-6">
        <h1 className="text-7xl font-light text-slate-500">404</h1>
        <h2 className="text-2xl font-medium">Page Not Found</h2>
        <p className="text-slate-400">The page <span className="font-medium text-slate-200">"{pageName}"</span> is not available in this Hub build.</p>
        {isFetched && authData?.isAuthenticated && authData?.user?.role === 'admin' && (
          <div className="p-4 bg-slate-900 rounded-lg border border-slate-800 text-left text-sm text-slate-300">
            Admin note: confirm this route is registered in <code>src/App.jsx</code> before treating it as missing functionality.
          </div>
        )}
        <Link to="/" className="inline-flex px-4 py-2 rounded-md bg-sky-600 hover:bg-sky-500 text-white">Return to Hub</Link>
      </div>
    </div>
  );
}
