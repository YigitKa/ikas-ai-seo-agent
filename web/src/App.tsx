import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense, lazy } from 'react';
import ErrorBoundary from './shared/ui/ErrorBoundary';
import { ToastProvider } from './shared/ui/Toast';
import { ThemeProvider } from './theme/ThemeContext';

const HomePage = lazy(() => import('./pages/HomePage'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/settings/SettingsPage'));
const LlmsLab = lazy(() => import('./pages/LlmsLab'));
const BatchOperations = lazy(() => import('./pages/BatchOperations'));
const Diagnostics = lazy(() => import('./pages/Diagnostics'));
const PromptEditor = lazy(() => import('./pages/prompts/PromptEditorPage'));
const SkillStudio = lazy(() => import('./pages/skills/SkillStudioPage'));
const Reports = lazy(() => import('./pages/Reports'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 300_000,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
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
              <Route path="/" element={<HomePage />} />
              <Route path="/workspace" element={<Dashboard />} />
              <Route path="/llms" element={<LlmsLab />} />
              <Route path="/diagnostics" element={<Diagnostics />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/batch" element={<BatchOperations />} />
              <Route path="/prompts" element={<PromptEditor />} />
              <Route path="/skills" element={<SkillStudio />} />
              <Route path="/reports" element={<Reports />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
        </ToastProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
