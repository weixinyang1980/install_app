const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("zlm", {
  meta: () => ipcRenderer.invoke("zlm:meta"),
  openExternal: (url) => ipcRenderer.invoke("zlm:open-external", url),
  runInstall: (payload) => ipcRenderer.invoke("zlm:run-install", payload),
  abortInstall: () => ipcRenderer.invoke("zlm:abort-install"),
  probe: (slug) => ipcRenderer.invoke("zlm:probe", slug),
  probeAll: (slugs) => ipcRenderer.invoke("zlm:probe-all", slugs),
  probeAfterInstall: (slug) => ipcRenderer.invoke("zlm:probe-after-install", slug),
  onInstallLog: (cb) => {
    const listener = (_e, data) => cb(data);
    ipcRenderer.on("zlm:install-log", listener);
    return () => ipcRenderer.removeListener("zlm:install-log", listener);
  },
  onInstallDone: (cb) => {
    const listener = (_e, data) => cb(data);
    ipcRenderer.on("zlm:install-done", listener);
    return () => ipcRenderer.removeListener("zlm:install-done", listener);
  },
});
