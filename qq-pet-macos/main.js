// macOS: 全局 EPIPE 防护 — 必须在最前面
// 原项目有几百个 console.log，管道断开时会 EPIPE 崩溃
const _origLog = console.log;
const _origErr = console.error;
const _origWarn = console.warn;
const safeFn = (fn) => (...args) => { try { fn(...args); } catch (e) { if (e?.code !== "EPIPE") throw e; } };
console.log = safeFn(_origLog);
console.error = safeFn(_origErr);
console.warn = safeFn(_origWarn);
process.stdout?.on?.("error", () => {});
process.stderr?.on?.("error", () => {});
process.on("uncaughtException", (err) => {
  if (err.code === "EPIPE" || err.message?.includes("EPIPE")) return;
  try {
    _origErr("[main] uncaughtException:", err);
  } catch (_) {}
});
process.on("unhandledRejection", (reason) => {
  try {
    _origErr("[main] unhandledRejection:", reason);
  } catch (_) {}
});

const { app, dialog } = require("electron");
const path = require("path");
const { ensureBackendStarted, stopBackend, getBackendLogPath } = require("./backend-service");

const gotTheLock = app.requestSingleInstanceLock();

// 禁用测试后门
global.$test = false;

global.initData = {};

let useTool = null;
let tool = ["floatStyle"];

try {
  let e = process.argv;
  for (let t in tool) {
    let a = false;
    for (let o in e) {
      if (e[o].indexOf(tool[t]) !== -1) {
        initData.NODE_TOOL = tool[t];
        a = true;
        break;
      }
    }
    if (a) break;
  }
} catch (e) {}

if (process?.env?.NODE_TOOL) {
  initData.NODE_TOOL = process.env.NODE_TOOL;
}

if (initData?.NODE_TOOL && typeof initData?.NODE_TOOL === "string") {
  useTool = require("./src/windows/tool/" + initData.NODE_TOOL + "/main.js");
}

const createWindow = async () => {
  require("./src/ini/init.js");
  process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = "true";
  process.on("unhandledRejection", function (e, t) {});
  app.setAppUserModelId("pet");

  if (gotTheLock) {
    if (useTool) {
      useTool.cleate("only");
    } else {
      require("./src/ini/doMain.js");
      const { startDataWatcher } = require("./src/ini/dataWatcher.js");
      startDataWatcher();
    }
  } else {
    app.exit(true);
  }
};

// macOS: 不加载 PepFlash DLL（使用 Ruffle WASM 替代）
app.commandLine.appendSwitch("disable-site-isolation-trials");

app.whenReady().then(() => {
  ensureBackendStarted()
    .then((ok) => {
      if (!ok) {
        dialog.showErrorBox(
          "AI 后端启动失败",
          `内置 Python 服务没有成功启动。\n\n请检查日志：\n${getBackendLogPath()}`
        );
      }
      return ok;
    })
    .catch((error) => {
      console.error("[backend] failed to start", error);
      try {
        dialog.showErrorBox(
          "AI 后端启动失败",
          `${error?.message || error}\n\n请检查日志：\n${getBackendLogPath()}`
        );
      } catch (_) {}
      return false;
    })
    .finally(() => {
      createWindow();
    });
});

app.on("before-quit", () => {
  stopBackend();
});
