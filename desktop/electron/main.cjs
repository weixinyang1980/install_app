const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const os = require("os");
const { spawn, spawnSync } = require("child_process");

let mainWindow = null;
let child = null;
let aborting = false;

function killInstallTree() {
  if (!child) return;
  const pid = child.pid;
  try {
    if (process.platform === "win32" && pid) {
      spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true, timeout: 8000 });
    } else {
      child.kill("SIGTERM");
    }
  } catch {
    try {
      child.kill();
    } catch {}
  }
  child = null;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 680,
    title: "装了吗",
    backgroundColor: "#0E2A3A",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5173";
  if (!app.isPackaged) {
    mainWindow.loadURL(devUrl);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

function send(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, payload);
  }
}

function detectPlatform() {
  if (process.platform === "win32") return "windows";
  if (process.platform === "darwin") return "macos";
  return "linux";
}

ipcMain.handle("zlm:meta", () => ({
  platform: detectPlatform(),
  raw: process.platform,
}));

ipcMain.handle("zlm:probe", async (_e, slug) => {
  const { probeSlug } = require("./detect.cjs");
  return probeSlug(String(slug || ""));
});

ipcMain.handle("zlm:probe-all", async (_e, slugs) => {
  const { probeMany } = require("./detect.cjs");
  return probeMany(Array.isArray(slugs) ? slugs : []);
});

ipcMain.handle("zlm:probe-after-install", async (_e, slug) => {
  const { probeUntilInstalled } = require("./detect.cjs");
  return probeUntilInstalled(String(slug || ""));
});

ipcMain.handle("zlm:open-external", async (_e, url) => {
  if (typeof url === "string" && /^https?:\/\//i.test(url)) {
    await shell.openExternal(url);
    return true;
  }
  return false;
});

ipcMain.handle("zlm:abort-install", () => {
  aborting = true;
  killInstallTree();
  send("zlm:install-log", { type: "system", text: "用户取消了安装。" });
  send("zlm:install-done", { code: -1, aborted: true });
  return true;
});

ipcMain.handle("zlm:run-install", async (_e, payload) => {
  const { script, language, elevate } = payload || {};
  if (!script || !String(script).trim()) {
    return { ok: false, error: "这份方案没有可执行脚本，请改走官方下载页。" };
  }

  if (child) {
    return { ok: false, error: "已经有一个安装在跑，先等它结束或点取消。" };
  }

  const platform = detectPlatform();
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const ext = language === "bash" || platform !== "windows" ? ".sh" : ".ps1";
  const file = path.join(os.tmpdir(), `zlm-install-${stamp}${ext}`);
  const body = String(script).replace(/\r\n/g, "\n").replace(/\n/g, "\r\n");
  fs.writeFileSync(file, "\uFEFF" + body, "utf8");

  let cmd;
  let args;
  if (platform === "windows") {
    if (elevate) {
      cmd = "powershell.exe";
      const inner = `-NoProfile -ExecutionPolicy Bypass -File "${file}"`;
      args = [
        "-NoProfile",
        "-Command",
        `Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList '${inner.replace(/'/g, "''")}'`,
      ];
    } else {
      cmd = "powershell.exe";
      args = ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", file];
    }
  } else {
    fs.chmodSync(file, 0o755);
    cmd = "/bin/bash";
    args = [file];
  }

  send("zlm:install-log", { type: "system", text: `开始执行 ${path.basename(file)}` });

  aborting = false;
  return await new Promise((resolve) => {
    child = spawn(cmd, args, {
      windowsHide: !elevate,
      env: {
        ...process.env,
        PYTHONUTF8: "1",
      },
    });

    const pump = (buf, type) => {
      const text = buf.toString("utf8");
      text.split(/\r?\n/).forEach((line) => {
        if (line.trim()) send("zlm:install-log", { type, text: line });
      });
    };
    child.stdout.on("data", (d) => pump(d, "stdout"));
    child.stderr.on("data", (d) => pump(d, "stderr"));
    child.on("error", (err) => {
      send("zlm:install-log", { type: "stderr", text: String(err) });
    });
    child.on("close", (code) => {
      const wasAbort = aborting;
      aborting = false;
      child = null;
      if (wasAbort) {
        resolve({ ok: false, code: -1, aborted: true });
        return;
      }
      send("zlm:install-done", { code: code ?? 1, aborted: false });
      resolve({ ok: code === 0, code });
    });
  });
});
