import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense, lazy } from 'react';
import ErrorBoundary from './shared/ui/ErrorBoundary';
import { ToastProvider } from './shared/ui/Toast';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/settings/SettingsPage'));
const LlmsLab = lazy(() => import('./pages/LlmsLab'));
const BatchOperations = lazy(() => import('./pages/BatchOperations'));
const PromptEditor = lazy(() => import('./pages/prompts/PromptEditorPage'));
const Reports = lazy(() => import('./pages/Reports'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
        <BrowserRouter>
          <Suspense
            fallback={
              <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-200">
                Yukleniyor...
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/llms" element={<LlmsLab />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/batch" element={<BatchOperations />} />
              <Route path="/prompts" element={<PromptEditor />} />
              <Route path="/reports" element={<Reports />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
