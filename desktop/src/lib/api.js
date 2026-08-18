const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8765";

async function req(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new Error("后端连不上。确认服务端开着：http://127.0.0.1:8765");
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const msg = data?.detail || data?.message || res.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

export const api = {
  health: () => req("/api/health"),
  presets: () => req("/api/presets"),
  parse: (query) => req("/api/parse", { method: "POST", body: JSON.stringify({ query }) }),
  versions: (slug) => req(`/api/software/${slug}/versions`),
  generate: (payload) => req("/api/plans/generate", { method: "POST", body: JSON.stringify(payload) }),
  feedback: (id, payload) => req(`/api/plans/${id}/feedback`, { method: "POST", body: JSON.stringify(payload) }),
};
