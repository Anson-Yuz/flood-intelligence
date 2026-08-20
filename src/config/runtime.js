export const isStaticDemo = import.meta.env.VITE_STATIC_DEMO === "true";

export function assetPath(path) {
  const normalized = String(path).replace(/^\/+/, "");
  return import.meta.env.BASE_URL + normalized;
}
