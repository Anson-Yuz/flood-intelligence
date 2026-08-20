import { isStaticDemo } from "../config/runtime";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const DEFAULT_TIMEOUT = 4500;

async function request(path, options = {}, fallbackFactory) {
  if (isStaticDemo) {
    if (!fallbackFactory) throw new Error("公开演示模式不连接后端服务");
    return {
      ...fallbackFactory(new Error("static-demo")),
      mode: "static",
      fallbackReason: "static-demo",
    };
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout ?? DEFAULT_TIMEOUT);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...options.headers,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("API returned a non-JSON response");
    }

    return { ...(await response.json()), mode: "api" };
  } catch (error) {
    if (!fallbackFactory) throw error;
    await new Promise((resolve) => window.setTimeout(resolve, 320));
    return {
      ...fallbackFactory(error),
      mode: "mock",
      fallbackReason: error.name === "AbortError" ? "timeout" : "unavailable",
    };
  } finally {
    window.clearTimeout(timeout);
  }
}

export function publishWarning(eventId, payload) {
  return request(
    `/events/${eventId}/publish`,
    { method: "POST", body: JSON.stringify(payload) },
    () => ({
      ok: true,
      eventId,
      publishedAt: new Date().toISOString(),
      receiptId: `MOCK-PUB-${Date.now()}`,
      channels: payload.channels,
    }),
  );
}

export function sendForManualReview(eventId, payload) {
  return request(
    `/events/${eventId}/manual-review`,
    { method: "POST", body: JSON.stringify(payload) },
    () => ({
      ok: true,
      eventId,
      queuedAt: new Date().toISOString(),
      queue: "防汛人工复核队列",
      reason: payload.reason,
    }),
  );
}

export function getRawEvidence(eventId) {
  return request(
    `/events/${eventId}/evidence`,
    { method: "GET" },
    () => ({
      ok: true,
      eventId,
      capturedAt: "2026-07-10 14:32:18.116",
      frameId: "FRAME-YJ017-143218-0881",
      imageQuality: 92,
      effectivePixels: 82,
      demVersion: "DEM-017-20260701",
      demAgeDays: 9,
      boundaryIou: 0.84,
      maximumDepth: 22,
      floodedArea: 286,
      floodedVolume: 42.7,
      confidence: 94,
      checksum: "73b5f63297e7be2fb31a8f2df066bda90e037cd71c02cbc388ab49706e2bd11d",
    }),
  );
}

export function getPlatformSnapshot() {
  return request(
    "/snapshot",
    { method: "GET" },
    () => ({ ok: true, updatedAt: new Date().toISOString(), source: "local-demo-data" }),
  );
}
