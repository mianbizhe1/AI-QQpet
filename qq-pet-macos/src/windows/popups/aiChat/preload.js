(() => {
  const _require = eval("require");
  const { contextBridge, ipcRenderer } = _require("electron");

  contextBridge.exposeInMainWorld("electronAPI", {
    aiChat_h_bus: (payload) => ipcRenderer.send("aiChat_h_bus_m", payload),
    aiChat_m_bus: (handler) => ipcRenderer.on("aiChat_m_bus_h", handler),
    // 截图 API - 返回 Promise
    captureScreenshot: () => ipcRenderer.invoke("screenshot_capture"),
  });
})();
