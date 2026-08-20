import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  AuthApiError,
  currentUserRequest,
  extractAuthenticatedUser,
  loginRequest,
  logoutRequest,
} from "./api";
import { isStaticDemo } from "../config/runtime";

const AuthContext = createContext(null);
const REMEMBER_USERNAME_KEY = "yujian.rememberedUsername";
const STATIC_DEMO_SESSION_KEY = "yujian.staticDemoSession";
const STATIC_DEMO_USER = {
  id: "public-demo",
  username: "visitor",
  displayName: "公开访客",
  role: "只读演示",
  tenantId: "public-showcase",
};

function readRememberedUsername() {
  try {
    return window.localStorage.getItem(REMEMBER_USERNAME_KEY) || "";
  } catch {
    return "";
  }
}

function writeRememberedUsername(username, remember) {
  try {
    if (remember) window.localStorage.setItem(REMEMBER_USERNAME_KEY, username);
    else window.localStorage.removeItem(REMEMBER_USERNAME_KEY);
  } catch {
    // Storage may be unavailable in privacy-restricted browser contexts.
  }
}

function readStaticDemoSession() {
  try {
    return window.sessionStorage.getItem(STATIC_DEMO_SESSION_KEY) === "active";
  } catch {
    return false;
  }
}

function writeStaticDemoSession(active) {
  try {
    if (active) window.sessionStorage.setItem(STATIC_DEMO_SESSION_KEY, "active");
    else window.sessionStorage.removeItem(STATIC_DEMO_SESSION_KEY);
  } catch {
    // Session storage is optional; the current in-memory session still works.
  }
}

export function AuthProvider({ children }) {
  const hasStaticSession = isStaticDemo && readStaticDemoSession();
  const [user, setUser] = useState(() => (hasStaticSession ? STATIC_DEMO_USER : null));
  const [status, setStatus] = useState(() => (hasStaticSession ? "authenticated" : "checking"));
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [rememberedUsername, setRememberedUsername] = useState(readRememberedUsername);

  const clearError = useCallback(() => setError(""), []);

  const enterStaticDemo = useCallback(() => {
    writeStaticDemoSession(true);
    setError("");
    setUser(STATIC_DEMO_USER);
    setStatus("authenticated");
    return STATIC_DEMO_USER;
  }, []);

  const refreshSession = useCallback(async () => {
    setStatus("checking");
    if (isStaticDemo) {
      const nextUser = readStaticDemoSession() ? STATIC_DEMO_USER : null;
      setUser(nextUser);
      setStatus(nextUser ? "authenticated" : "unauthenticated");
      return nextUser;
    }

    try {
      const payload = await currentUserRequest();
      const nextUser = extractAuthenticatedUser(payload);
      setUser(nextUser);
      setStatus(nextUser ? "authenticated" : "unauthenticated");
      return nextUser;
    } catch (requestError) {
      setUser(null);
      setStatus("unauthenticated");
      if (!(requestError instanceof AuthApiError && requestError.status === 401)) {
        setError(requestError.message || "会话校验失败");
      }
      return null;
    }
  }, []);

  useEffect(() => {
    refreshSession();
  }, [refreshSession]);

  const login = useCallback(async ({ username, password, remember }) => {
    if (isStaticDemo) return enterStaticDemo();

    setIsSubmitting(true);
    setError("");
    try {
      const payload = await loginRequest({ username, password, remember });
      let nextUser = extractAuthenticatedUser(payload);
      if (!nextUser) {
        nextUser = extractAuthenticatedUser(await currentUserRequest());
      }
      if (!nextUser) throw new AuthApiError("登录成功，但未获取到用户信息");
      writeRememberedUsername(username, remember);
      setRememberedUsername(remember ? username : "");
      setUser(nextUser);
      setStatus("authenticated");
      return nextUser;
    } catch (requestError) {
      const message = requestError?.message || "登录失败，请稍后重试";
      setError(message);
      setUser(null);
      setStatus("unauthenticated");
      throw requestError;
    } finally {
      setIsSubmitting(false);
    }
  }, [enterStaticDemo]);

  const logout = useCallback(async () => {
    setIsLoggingOut(true);
    setError("");
    try {
      if (isStaticDemo) {
        writeStaticDemoSession(false);
      } else {
        await logoutRequest();
      }
    } finally {
      setUser(null);
      setStatus("unauthenticated");
      setIsLoggingOut(false);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      status,
      error,
      isChecking: status === "checking",
      isAuthenticated: status === "authenticated" && Boolean(user),
      isSubmitting,
      isLoggingOut,
      isStaticDemo,
      rememberedUsername,
      login,
      logout,
      enterStaticDemo,
      refreshSession,
      clearError,
    }),
    [
      user,
      status,
      error,
      isSubmitting,
      isLoggingOut,
      rememberedUsername,
      login,
      logout,
      enterStaticDemo,
      refreshSession,
      clearError,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
