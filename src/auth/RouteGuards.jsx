import { Navigate, useLocation } from "react-router-dom";
import { WaveSine } from "@phosphor-icons/react";
import { useAuth } from "./AuthContext";

export function AuthLoadingScreen() {
  return (
    <main className="auth-loading-screen" aria-live="polite" aria-busy="true">
      <div className="auth-loading-mark"><WaveSine size={28} weight="bold" /></div>
      <strong>正在恢复安全会话</strong>
      <span>请稍候，正在验证登录状态…</span>
      <i aria-hidden="true" />
    </main>
  );
}

export function RequireAuth({ children }) {
  const { isChecking, isAuthenticated } = useAuth();
  const location = useLocation();

  if (isChecking) return <AuthLoadingScreen />;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  }
  return children;
}

export function PublicOnlyRoute({ children }) {
  const { isChecking, isAuthenticated } = useAuth();
  if (isChecking) return <AuthLoadingScreen />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return children;
}
