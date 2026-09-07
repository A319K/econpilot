import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Layout } from "./components/layout/Layout"
import { ToastProvider } from "./components/ui/Toast"
import { ApplicationDetailPage } from "./pages/ApplicationDetailPage"
import { PipelinePage } from "./pages/PipelinePage"
import { ProfilePage } from "./pages/ProfilePage"
import { QueuePage } from "./pages/QueuePage"
import { SettingsPage } from "./pages/SettingsPage"
import { StatsPage } from "./pages/StatsPage"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/queue" replace />} />
              <Route path="/queue" element={<QueuePage />} />
              <Route path="/pipeline" element={<PipelinePage />} />
              <Route path="/applications/:id" element={<ApplicationDetailPage />} />
              <Route path="/stats" element={<StatsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/queue" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  )
}

export default App
