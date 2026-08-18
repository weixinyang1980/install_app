import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Search, Download, Shield, RefreshCw } from "lucide-react";
import { api } from "./lib/api";
import { KIND_FLAVOR, PLATFORM_LABEL } from "./lib/utils";
import PlanView from "./components/PlanView";
import InstallConsole from "./components/InstallConsole";

const electronApi = typeof window !== "undefined" ? window.zlm : null;

function StatusPill({ status, compact = false }) {
  if (!status) {
    return <span className="rounded-full bg-black/10 px-2 py-0.5 text-[10px]">检测中</span>;
  }
  if (status.installed) {
    return (
      <span className="rounded-full bg-nori px-2 py-0.5 text-[10px] font-bold text-milk">
        装了{!compact && status.version ? ` · ${status.version.split("\n")[0].slice(0, 28)}` : ""}
      </span>
    );
  }
  return <span className="rounded-full bg-chili/90 px-2 py-0.5 text-[10px] font-bold text-milk">没装</span>;
}

export default function App() {
  const [platform, setPlatform] = useState("windows");
  const [query, setQuery] = useState("");
  const [presets, setPresets] = useState([]);
  const [software, setSoftware] = useState(null);
  const [versions, setVersions] = useState([]);
  const [version, setVersion] = useState("latest");
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [logs, setLogs] = useState([]);
  const [running, setRunning] = useState(false);
  const [comment, setComment] = useState("");
  const [statusBySlug, setStatusBySlug] = useState({});
  const softwareRef = useRef(null);
  softwareRef.current = software;

  function rememberStatus(row) {
    if (!row?.slug) return;
    setStatusBySlug((prev) => ({ ...prev, [row.slug]: row }));
  }

  async function probeOne(slug) {
    if (!slug || !electronApi?.probe) return null;
    const row = await electronApi.probe(slug);
    rememberStatus(row);
    return row;
  }

  async function probeList(slugs) {
    if (!electronApi?.probeAll || !slugs?.length) return;
    const rows = await electronApi.probeAll(slugs);
    setStatusBySlug((prev) => {
      const next = { ...prev };
      for (const row of rows) next[row.slug] = row;
      return next;
    });
  }

  useEffect(() => {
    (async () => {
      if (electronApi?.meta) {
        const meta = await electronApi.meta();
        if (meta?.platform) setPlatform(meta.platform);
      } else {
        const p = navigator.platform.toLowerCase();
        if (p.includes("mac")) setPlatform("macos");
        else if (p.includes("linux")) setPlatform("linux");
        else setPlatform("windows");
      }
      try {
        const data = await api.presets();
        const items = data.items || [];
        setPresets(items);
        await probeList(items.map((s) => s.slug));
      } catch (e) {
        setError(e.message || "柜台还没开门：后端没连上。");
      }
    })();
  }, []);

  useEffect(() => {
    if (!electronApi) return undefined;
    const offLog = electronApi.onInstallLog((line) => setLogs((xs) => [...xs, line]));
    const offDone = electronApi.onInstallDone(async (info) => {
      setRunning(false);
      if (info?.aborted) {
        setToast("已停手，页面可以拖了。");
        return;
      }
      const slug = softwareRef.current?.slug;
      if (!slug) return;
      const row = electronApi.probeAfterInstall
        ? await electronApi.probeAfterInstall(slug)
        : await electronApi.probe(slug);
      rememberStatus(row);
      if (row?.installed) {
        setError("");
        setToast(`盖章：装了！${row.version ? ` ${row.version}` : ""}`);
      } else {
        setToast("脚本结束了，但本机还是检测不到这个软件，算没装上。");
      }
    });
    return () => {
      offLog?.();
      offDone?.();
    };
  }, []);

  const flavor = KIND_FLAVOR[software?.kind] || KIND_FLAVOR.other;
  const currentStatus = software ? statusBySlug[software.slug] : null;
  const installed = currentStatus?.installed === true;

  async function pickSoftware(s) {
    setError("");
    setToast("");
    setPlan(null);
    setSoftware(s);
    setBusy("versions");
    probeOne(s.slug);
    try {
      const data = await api.versions(s.slug);
      setVersions(data.items || []);
      setVersion(data.default || data.items?.[0]?.version || "latest");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  async function onSearch(e) {
    e?.preventDefault();
    if (!query.trim()) return;
    setBusy("parse");
    setError("");
    try {
      const data = await api.parse(query.trim());
      await pickSoftware(data.software);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  }

  async function generate() {
    if (!software) return;
    setBusy("generate");
    setError("");
    setPlan(null);
    try {
      const data = await api.generate({
        slug: software.slug,
        version,
        platform,
        force: false,
      });
      setPlan(data);
      await probeOne(software.slug);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }

  async function copyScript() {
    if (!plan?.script) return;
    await navigator.clipboard.writeText(plan.script);
    setToast("脚本已抄走，去终端粘贴也能装。");
  }

  async function install({ elevate = false } = {}) {
    if (!plan) return;
    if (plan.official_url && !plan.script) {
      if (electronApi?.openExternal) await electronApi.openExternal(plan.official_url);
      else window.open(plan.official_url, "_blank");
      setToast("官方下载页已打开。装完后点「重新检测」。");
      return;
    }
    if (!electronApi?.runInstall) {
      await copyScript();
      setToast("当前是浏览器预览，已复制脚本。用 Electron 窗口才能直接安装。");
      return;
    }
    setLogs([]);
    setRunning(true);
    setError("");
    setToast("");
    try {
      await electronApi.runInstall({
        script: plan.script,
        language: plan.script_language,
        elevate,
      });
    } catch (e) {
      setRunning(false);
      setError(e.message);
    }
  }

  async function sendFeedback(isValid) {
    if (!plan) return;
    try {
      await api.feedback(plan.id, { is_valid: isValid, comment });
      setError("");
      setToast(isValid ? "记一笔：这包能吃。" : "记一笔：这包踩雷了。");
      setComment("");
    } catch (e) {
      setError(e.message);
    }
  }

  const headline = useMemo(() => {
    if (!software) return "今天你装了吗？";
    if (installed) return `${software.name} 装了`;
    if (currentStatus && !currentStatus.installed) return `${software.name} 还没装`;
    return `要不要来一份 ${software.name}？`;
  }, [software, installed, currentStatus]);

  return (
    <div className="shelf-bg min-h-full">
      <header className="flex items-center justify-between px-6 py-4">
        <div>
          <p className="font-display text-sm tracking-[0.35em] text-lantern">NIGHT STALL · 安装小卖部</p>
          <h1 className="font-display text-4xl font-bold text-milk">{headline}</h1>
        </div>
        <div className={`stamp px-4 py-2 text-xl ${installed ? "stamp-ok" : "opacity-70"}`}>
          {software ? (installed ? "装了！" : "没装") : "待点"}
        </div>
      </header>

      <main className="grid gap-6 px-6 pb-10 lg:grid-cols-[360px_1fr]">
        <section className="space-y-4">
          <form onSubmit={onSearch} className="rounded-3xl border-2 border-ink bg-paper p-4 text-ink shadow-stamp">
            <label className="font-display text-sm">柜台上喊一声</label>
            <div className="mt-2 flex gap-2">
              <input
                className="w-full rounded-2xl border-2 border-ink bg-milk px-3 py-2 outline-none"
                placeholder='比如「我想装 MySQL」'
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <button className="rounded-2xl bg-chili px-3 text-milk shadow-stamp" type="submit">
                <Search size={18} />
              </button>
            </div>
          </form>

          <div className="rounded-3xl border-2 border-ink bg-[#143445] p-4 shadow-stamp">
            <div className="mb-3 flex items-center justify-between">
              <p className="font-display text-lantern">常见存货</p>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs text-paper/80"
                onClick={() => probeList(presets.map((s) => s.slug))}
              >
                <RefreshCw size={12} /> 重新检测
              </button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {presets.map((s) => {
                const k = KIND_FLAVOR[s.kind] || KIND_FLAVOR.other;
                const st = statusBySlug[s.slug];
                return (
                  <button
                    key={s.slug}
                    type="button"
                    onClick={() => pickSoftware(s)}
                    className={`pack rounded-2xl border-2 border-ink px-3 py-2 text-left text-ink shadow-stamp ${k.color}`}
                  >
                    <span className="flex items-center justify-between gap-1">
                      <span className="text-[10px] opacity-70">{k.tag}</span>
                      <StatusPill status={st} compact />
                    </span>
                    <span className="font-display text-sm font-bold">{s.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <section className="space-y-4">
          {error ? (
            <div className="rounded-2xl border-2 border-chili bg-[#3a1510] px-4 py-3 text-sm">{error}</div>
          ) : null}
          {toast ? (
            <div className="rounded-2xl border-2 border-nori bg-[#10281c] px-4 py-3 text-sm text-paper">{toast}</div>
          ) : null}

          {software ? (
            <div className="rounded-3xl border-2 border-ink bg-paper p-5 text-ink shadow-stamp">
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <p className="text-xs">
                    {flavor.tag} · {software.slug}
                  </p>
                  <h3 className="font-display text-3xl">{software.name}</h3>
                  <p className="mt-1 text-sm">
                    本机：{installed ? `装了${currentStatus.version ? ` · ${currentStatus.version}` : ""}` : currentStatus ? "没装" : "正在检测"}
                  </p>
                </div>
                <label className="text-sm">
                  版本
                  <select
                    className="ml-2 rounded-xl border-2 border-ink bg-milk px-2 py-1"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                  >
                    {versions.map((v) => (
                      <option key={v.version} value={v.version}>
                        {v.version}
                        {v.channel && v.channel !== "stable" ? ` (${v.channel})` : ""}
                        {v.is_latest_stable ? " · 默认" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm">
                  平台
                  <select
                    className="ml-2 rounded-xl border-2 border-ink bg-milk px-2 py-1"
                    value={platform}
                    onChange={(e) => setPlatform(e.target.value)}
                  >
                    {Object.entries(PLATFORM_LABEL).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={generate}
                  disabled={busy === "generate"}
                  className="rounded-2xl bg-chili px-4 py-2 font-display text-milk shadow-stamp disabled:opacity-60"
                >
                  {busy === "generate" ? "仓库翻方案中…" : "出一份安装小票"}
                </button>
                <button
                  type="button"
                  onClick={() => probeOne(software.slug)}
                  className="rounded-2xl bg-ink px-3 py-2 text-sm text-milk"
                >
                  重新检测
                </button>
              </div>
              {busy === "versions" || busy === "parse" ? (
                <p className="mt-3 inline-flex items-center gap-2 text-sm">
                  <Loader2 className="animate-spin" size={16} /> 老板正在仓库翻版本号…
                </p>
              ) : null}
            </div>
          ) : (
            <div className="rounded-3xl border-2 border-dashed border-paper/30 p-10 text-center text-paper/70">
              货架上的包装都可以点。或者直接喊软件名。绿标是已经装过的。
            </div>
          )}

          {plan ? (
            <>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => install({ elevate: false })}
                  className="inline-flex items-center gap-2 rounded-2xl bg-nori px-4 py-2 font-display text-milk shadow-stamp"
                >
                  <Download size={16} /> {plan.script ? (installed ? "再装一遍" : "一键安装") : "打开官方下载页"}
                </button>
                {plan.script ? (
                  <button
                    type="button"
                    onClick={() => install({ elevate: true })}
                    className="inline-flex items-center gap-2 rounded-2xl bg-lantern px-4 py-2 font-display text-ink shadow-stamp"
                  >
                    <Shield size={16} /> 提权安装
                  </button>
                ) : null}
                {plan.script ? (
                  <button type="button" onClick={copyScript} className="rounded-2xl bg-paper px-4 py-2 font-display text-ink shadow-stamp">
                    复制整段脚本
                  </button>
                ) : null}
              </div>
              {plan.script ? (
                <InstallConsole
                  lines={logs}
                  running={running}
                  onAbort={() => {
                    setRunning(false);
                    electronApi?.abortInstall();
                  }}
                />
              ) : null}
              <PlanView plan={plan} />
              <div className="rounded-3xl border-2 border-ink bg-[#143445] p-4">
                <p className="mb-2 font-display text-lantern">这包靠谱吗？</p>
                <div className="flex flex-wrap gap-2">
                  <button className="rounded-full bg-nori px-4 py-1 text-sm" type="button" onClick={() => sendFeedback(true)}>
                    有效
                  </button>
                  <button className="rounded-full bg-chili px-4 py-1 text-sm" type="button" onClick={() => sendFeedback(false)}>
                    无效
                  </button>
                </div>
                <textarea
                  className="mt-3 w-full rounded-2xl border-2 border-ink bg-paper p-2 text-sm text-ink"
                  rows={2}
                  placeholder="想骂两句或补充坑点，写这儿。"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
              </div>
            </>
          ) : null}
        </section>
      </main>
    </div>
  );
}
