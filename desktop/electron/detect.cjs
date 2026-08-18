const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

function refreshProcessPath() {
  if (process.platform !== "win32") return;
  try {
    const out = spawnSync(
      "powershell.exe",
      [
        "-NoProfile",
        "-Command",
        "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')",
      ],
      { encoding: "utf8", windowsHide: true, timeout: 8000 },
    );
    const p = (out.stdout || "").trim();
    if (p) {
      process.env.Path = p;
      process.env.PATH = p;
    }
  } catch {
    // keep existing PATH
  }
}

function expandGlobs(patterns) {
  const hits = [];
  for (const pattern of patterns || []) {
    if (!pattern) continue;
    if (!pattern.includes("*")) {
      if (fs.existsSync(pattern)) hits.push(pattern);
      continue;
    }
    const parts = pattern.split(/[/\\]/);
    let candidates = [parts[0].endsWith(":") ? parts[0] + "\\" : parts[0] || "/"];
    for (let i = 1; i < parts.length; i++) {
      const piece = parts[i];
      const next = [];
      for (const dir of candidates) {
        if (!fs.existsSync(dir)) continue;
        try {
          if (piece === "*") {
            for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
              next.push(path.join(dir, ent.name));
            }
          } else if (piece.includes("*")) {
            const re = new RegExp("^" + piece.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$", "i");
            for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
              if (re.test(ent.name)) next.push(path.join(dir, ent.name));
            }
          } else {
            next.push(path.join(dir, piece));
          }
        } catch {
          // skip unreadable
        }
      }
      candidates = next;
    }
    for (const c of candidates) {
      if (fs.existsSync(c)) hits.push(c);
    }
  }
  return hits;
}

function runVersion(binPath, args) {
  const r = spawnSync(binPath, args, {
    encoding: "utf8",
    timeout: 8000,
    windowsHide: true,
    env: process.env,
  });
  const text = `${r.stdout || ""}\n${r.stderr || ""}`.trim();
  const line = text.split(/\r?\n/).map((s) => s.trim()).find(Boolean) || "";
  return { ok: r.error ? false : r.status === 0 || Boolean(line), line, status: r.status };
}

const DETECTORS = {
  git: { bins: ["git"], args: ["--version"], globs: ["C:\\Program Files\\Git\\cmd\\git.exe"] },
  nodejs: { bins: ["node"], args: ["-v"], globs: ["C:\\Program Files\\nodejs\\node.exe"] },
  python: {
    bins: ["python", "py"],
    args: ["--version"],
    globs: [
      path.join(os.homedir(), "AppData\\Local\\Programs\\Python\\*\\python.exe"),
      "C:\\Program Files\\Python*\\python.exe",
    ],
  },
  jdk: {
    bins: ["java"],
    args: ["-version"],
    globs: [
      "C:\\Program Files\\Eclipse Adoptium\\*\\bin\\java.exe",
      "C:\\Program Files\\Microsoft\\jdk-*\\bin\\java.exe",
      "C:\\Program Files\\Java\\*\\bin\\java.exe",
    ],
  },
  mysql: {
    bins: ["mysql"],
    args: ["--version"],
    globs: ["C:\\Program Files\\MySQL\\MySQL Server *\\bin\\mysql.exe"],
  },
  maven: { bins: ["mvn"], args: ["-version"] },
  redis: { bins: ["redis-server", "memurai"], args: ["--version"] },
  docker: { bins: ["docker"], args: ["--version"] },
  nginx: {
    bins: ["nginx"],
    args: ["-v"],
    globs: [path.join(os.homedir(), "nginx\\nginx.exe")],
  },
  go: { bins: ["go"], args: ["version"], globs: ["C:\\Program Files\\Go\\bin\\go.exe"] },
  rust: {
    bins: ["rustc"],
    args: ["--version"],
    globs: [path.join(os.homedir(), ".cargo\\bin\\rustc.exe")],
  },
  mongodb: { bins: ["mongod"], args: ["--version"] },
  postgresql: {
    bins: ["psql"],
    args: ["--version"],
    globs: [
      "C:\\Program Files\\PostgreSQL\\*\\bin\\psql.exe",
      "C:\\Program Files (x86)\\PostgreSQL\\*\\bin\\psql.exe",
    ],
  },
  vscode: {
    bins: ["code"],
    args: ["--version"],
    globs: [
      path.join(process.env.LOCALAPPDATA || "", "Programs\\Microsoft VS Code\\Code.exe"),
      "C:\\Program Files\\Microsoft VS Code\\Code.exe",
    ],
  },
  idea: {
    bins: ["idea64", "idea"],
    args: ["--version"],
    globs: [
      "C:\\Program Files\\JetBrains\\IntelliJ IDEA*\\bin\\idea64.exe",
      path.join(process.env.LOCALAPPDATA || "", "Programs\\IntelliJ IDEA*\\bin\\idea64.exe"),
    ],
  },
  homebrew: { bins: ["brew"], args: ["--version"] },
  nvm: {
    bins: ["nvm"],
    args: ["version"],
    globs: [path.join(process.env.APPDATA || "", "nvm\\nvm.exe")],
  },
};

function which(bin) {
  const cmd = process.platform === "win32" ? "where" : "which";
  const r = spawnSync(cmd, [bin], {
    encoding: "utf8",
    timeout: 5000,
    windowsHide: true,
    env: process.env,
  });
  const line = (r.stdout || "").split(/\r?\n/).map((s) => s.trim()).find((s) => s && fs.existsSync(s));
  return line || null;
}

function probeSlug(slug) {
  refreshProcessPath();
  const spec = DETECTORS[slug] || { bins: [slug], args: ["--version"], globs: [] };
  const args = spec.args || ["--version"];
  const tried = [];

  for (const bin of spec.bins || []) {
    const found = which(bin);
    if (found) {
      const ver = runVersion(found, args);
      if (ver.ok || ver.line) {
        return { slug, installed: true, version: ver.line, path: found };
      }
      tried.push(found);
    }
  }

  for (const file of expandGlobs(spec.globs)) {
    if (!fs.existsSync(file)) continue;
    const ver = runVersion(file, args);
    if (ver.ok || ver.line || file.toLowerCase().endsWith(".exe")) {
      return { slug, installed: true, version: ver.line || path.basename(file), path: file };
    }
    tried.push(file);
  }

  return { slug, installed: false, version: "", path: "", tried };
}

function probeMany(slugs) {
  refreshProcessPath();
  return (slugs || []).map((slug) => probeSlug(slug));
}

async function probeUntilInstalled(slug, attempts = 8, delayMs = 400) {
  let last = probeSlug(slug);
  for (let i = 0; i < attempts && !last.installed; i++) {
    await new Promise((r) => setTimeout(r, delayMs));
    last = probeSlug(slug);
  }
  return last;
}

module.exports = { probeSlug, probeMany, probeUntilInstalled, refreshProcessPath };
