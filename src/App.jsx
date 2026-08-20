import { BrowserRouter, HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { PublicOnlyRoute, RequireAuth } from "./auth/RouteGuards";
import { AppShell } from "./components/AppShell";
import { AlertVisualProvider } from "./context/AlertVisualContext";
import { AuditPage } from "./pages/AuditPage";
import { DevicesPage } from "./pages/DevicesPage";
import { EventsPage } from "./pages/EventsPage";
import { LoginPage } from "./pages/LoginPage";
import { MaintenancePage } from "./pages/MaintenancePage";
import { OverviewPage } from "./pages/OverviewPage";
import { ReviewPage } from "./pages/ReviewPage";
import { SimulatorPage } from "./pages/SimulatorPage";
import { isStaticDemo } from "./config/runtime";
import "./auth/auth.css";

export function App() {
  const Router = isStaticDemo ? HashRouter : BrowserRouter;

  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AlertVisualProvider>
          <Routes>
            <Route
              path="login"
              element={
                <PublicOnlyRoute>
                  <LoginPage />
                </PublicOnlyRoute>
              }
            />
            <Route
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
              <Route index element={<ReviewPage />} />
              <Route path="overview" element={<OverviewPage />} />
              <Route path="events" element={<EventsPage />} />
              <Route path="simulator" element={<SimulatorPage />} />
              <Route path="maintenance" element={<MaintenancePage />} />
              <Route path="devices" element={<DevicesPage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </AlertVisualProvider>
      </AuthProvider>
    </Router>
  );
}
