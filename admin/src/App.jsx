import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8765";

async function req(path, { token, method = "GET", body } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Admin-Token": token } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("zlm_admin") || "");
  const [password, setPassword] = useState("");
  const [tab, setTab] = useState("plans");
  const [plans, setPlans] = useState([]);
  const [feedbacks, setFeedbacks] = useState([]);
  const [stats, setStats] = useState([]);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const authed = Boolean(token);

  async function login(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await req("/api/admin/login", { method: "POST", body: { password } });
      localStorage.setItem("zlm_admin", data.token);
      setToken(data.token);
    } catch (err) {
      setError(err.message);
    }
  }

  function logout() {
    localStorage.removeItem("zlm_admin");
    setToken("");
  }

  async function refresh() {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      const [p, f, s] = await Promise.all([
        req("/api/admin/plans", { token }),
        req("/api/admin/feedbacks", { token }),
        req("/api/stats"),
      ]);
      setPlans(p.items || []);
      setFeedbacks(f.items || []);
      setStats(s.items || []);
    } catch (err) {
      setError(err.message);
      if (String(err.message).includes("未登录") || String(err.message).includes("登录失效")) logout();
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (token) refresh();
  }, [token]);

  async function savePlan() {
    if (!editing) return;
    await req(`/api/admin/plans/${editing.id}`, {
      token,
      method: "PUT",
      body: { markdown: editing.markdown, script: editing.script, official_url: editing.official_url },
    });
    setEditing(null);
    refresh();
  }

  async function delPlan(id) {
    if (!confirm("撕掉这张小票？")) return;
    await req(`/api/admin/plans/${id}`, { token, method: "DELETE" });
    refresh();
  }

  async function regen(id) {
    setBusy(true);
    try {
      await req(`/api/admin/plans/${id}/regenerate`, { token, method: "POST" });
      refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function markFb(id) {
    await req(`/api/admin/feedbacks/${id}?status=handled`, { token, method: "PATCH" });
    refresh();
  }

  const pending = useMemo(() => feedbacks.filter((x) => x.status === "pending").length, [feedbacks]);

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <form onSubmit={login} className="w-full max-w-sm rounded-3xl border-2 border-ink bg-paper p-6 text-ink shadow-[4px_4px_0_0_#1A120C]">
          <p className="font-display text-sm text-chili">后厨账本</p>
          <h1 className="mb-4 font-display text-3xl">先报口令</h1>
          <input
            type="password"
            className="w-full rounded-2xl border-2 border-ink px-3 py-2"
            placeholder="ADMIN_PASSWORD"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error ? <p className="mt-2 text-sm text-chili">{error}</p> : null}
          <button className="mt-4 w-full rounded-2xl bg-chili py-2 font-display text-milk" type="submit">
            进门
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-lantern">装了吗 · 后厨</p>
          <h1 className="font-display text-3xl">账本打开了</h1>
        </div>
        <div className="flex gap-2">
          {["plans", "feedbacks", "stats"].map((t) => (
            <button
              key={t}
              className={`rounded-full px-4 py-1 ${tab === t ? "bg-lantern text-ink" : "bg-[#143445]"}`}
              onClick={() => setTab(t)}
            >
              {t === "plans" ? "方案" : t === "feedbacks" ? `反馈${pending ? ` (${pending})` : ""}` : "统计"}
            </button>
          ))}
          <button className="rounded-full bg-chili px-4 py-1" onClick={logout}>
            下班
          </button>
        </div>
      </header>
      {error ? <p className="mb-4 rounded-2xl bg-[#3a1510] p-3">{error}</p> : null}
      {busy ? <p className="mb-4 text-sm text-paper/70">翻账本中…</p> : null}

      {tab === "plans" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="space-y-2">
            {plans.map((p) => (
              <article key={p.id} className="rounded-2xl border-2 border-ink bg-[#143445] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-display text-lg">
                      {p.software?.name} · {p.version} · {p.platform}
                    </p>
                    <p className="text-xs opacity-70">
                      #{p.id} · 选了 {p.select_count} 次 · {p.source}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <button className="rounded-full bg-paper px-3 py-1 text-xs text-ink" onClick={() => setEditing({ ...p })}>
                      改
                    </button>
                    <button className="rounded-full bg-lantern px-3 py-1 text-xs text-ink" onClick={() => regen(p.id)}>
                      AI 重出
                    </button>
                    <button className="rounded-full bg-chili px-3 py-1 text-xs" onClick={() => delPlan(p.id)}>
                      撕掉
                    </button>
                  </div>
                </div>
              </article>
            ))}
            {plans.length === 0 ? <p>还没有小票。</p> : null}
          </div>
          {editing ? (
            <div className="rounded-2xl border-2 border-ink bg-paper p-4 text-ink">
              <h2 className="font-display text-xl">改小票 #{editing.id}</h2>
              <label className="mt-2 block text-sm">Markdown</label>
              <textarea
                className="h-64 w-full rounded-xl border-2 border-ink p-2 font-mono text-xs"
                value={editing.markdown}
                onChange={(e) => setEditing({ ...editing, markdown: e.target.value })}
              />
              <label className="mt-2 block text-sm">脚本</label>
              <textarea
                className="h-40 w-full rounded-xl border-2 border-ink p-2 font-mono text-xs"
                value={editing.script || ""}
                onChange={(e) => setEditing({ ...editing, script: e.target.value })}
              />
              <label className="mt-2 block text-sm">官方链接</label>
              <input
                className="w-full rounded-xl border-2 border-ink px-2 py-1"
                value={editing.official_url || ""}
                onChange={(e) => setEditing({ ...editing, official_url: e.target.value })}
              />
              <div className="mt-3 flex gap-2">
                <button className="rounded-full bg-nori px-4 py-1 text-milk" onClick={savePlan}>
                  存
                </button>
                <button className="rounded-full bg-ink px-4 py-1 text-milk" onClick={() => setEditing(null)}>
                  算了
                </button>
              </div>
            </div>
          ) : (
            <p className="text-paper/60">点「改」把小票摊开。</p>
          )}
        </div>
      ) : null}

      {tab === "feedbacks" ? (
        <div className="space-y-2">
          {feedbacks.map((f) => (
            <article key={f.id} className="rounded-2xl border-2 border-ink bg-[#143445] p-4">
              <p className="font-display">
                {f.software} {f.version} / {f.platform} · {f.is_valid === true ? "有效" : f.is_valid === false ? "无效" : "没打分"}
              </p>
              <p className="text-sm">{f.comment || "（没写字）"}</p>
              <p className="text-xs opacity-70">
                {f.status} · {f.created_at}
              </p>
              {f.status !== "handled" ? (
                <button className="mt-2 rounded-full bg-nori px-3 py-1 text-xs" onClick={() => markFb(f.id)}>
                  标记已处理
                </button>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {tab === "stats" ? (
        <table className="w-full overflow-hidden rounded-2xl border-2 border-ink bg-[#143445] text-left text-sm">
          <thead className="bg-nori">
            <tr>
              <th className="px-3 py-2">软件</th>
              <th>版本</th>
              <th>平台</th>
              <th>次数</th>
            </tr>
          </thead>
          <tbody>
            {stats.map((s) => (
              <tr key={s.plan_id} className="border-t border-white/10">
                <td className="px-3 py-2">{s.software}</td>
                <td>{s.version}</td>
                <td>{s.platform}</td>
                <td>{s.select_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
