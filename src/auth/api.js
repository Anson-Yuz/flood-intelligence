const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
const AUTH_BASE = `${API_BASE}/auth`;

export class AuthApiError extends Error {
  constructor(message, status = 0, body = null) {
    super(message);
    this.name = "AuthApiError";
    this.status = status;
    this.body = body;
  }
}

async function authRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${AUTH_BASE}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new AuthApiError("无法连接认证服务，请检查网络后重试");
  }

  let body = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    body = await response.json().catch(() => null);
  }

  if (!response.ok) {
    const message = body?.detail || body?.message || `认证请求失败（${response.status}）`;
    throw new AuthApiError(message, response.status, body);
  }

  return body;
}

export function loginRequest({ username, password, remember }) {
  return authRequest("/login", {
    method: "POST",
    body: JSON.stringify({ username, password, remember }),
  });
}

export function currentUserRequest() {
  return authRequest("/session", { method: "GET" });
}

export function logoutRequest() {
  return authRequest("/logout", { method: "POST" });
}

export function extractAuthenticatedUser(payload) {
  if (!payload || payload.authenticated === false) return null;
  return payload.user ?? payload.data?.user ?? null;
}
