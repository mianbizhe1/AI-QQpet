const { app } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawnSync } = require("child_process");

const HOST = "127.0.0.1";
const PORT = 18080;

let backendProcess = null;
let stopping = false;

function getBackendDataDir() {
  return path.join(app.getPath("userData"), "ai-backend");
}

function getBackendLogPath() {
  return path.join(getBackendDataDir(), "backend-launch.log");
}

function logLine(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try {
    fs.mkdirSync(getBackendDataDir(), { recursive: true });
    fs.appendFileSync(getBackendLogPath(), line, "utf8");
  } catch (_) {}
  try {
    console.log(line.trimEnd());
  } catch (_) {}
}

function getPackagedBackendExec() {
  const baseDir = process.resourcesPath;
  const candidates = [
    path.join(baseDir, "backend", "qqpet-ai-server", "qqpet-ai-server"),
    path.join(baseDir, "backend", "qqpet-ai-server", "qqpet-ai-server.exe"),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) || "";
}

function getDevBackendCommand() {
  const repoRoot = path.resolve(__dirname, "..");
  const scriptPath = path.join(repoRoot, "src", "backend_entry.py");
  const candidates = process.platform === "win32" ? ["py", "python"] : ["python3", "python"];

  for (const command of candidates) {
    const probe = spawnSync(command, ["--version"], {
      cwd: repoRoot,
      stdio: "ignore",
    });
    if (!probe.error && probe.status === 0) {
      logLine(`dev python command detected: ${command}`);
      return {
        command,
        args: [scriptPath],
        cwd: repoRoot,
      };
    }
  }

  return null;
}

function waitForHealth(timeoutMs = 15000) {
  const startedAt = Date.now();

  return new Promise((resolve) => {
    const probe = () => {
      const req = http.get(
        {
          hostname: HOST,
          port: PORT,
          path: "/health",
          timeout: 1500,
        },
        (res) => {
          if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
            res.resume();
            resolve(true);
            return;
          }
          res.resume();
          retry();
        }
      );

      req.on("error", retry);
      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - startedAt >= timeoutMs) {
        logLine(`backend health check timed out after ${timeoutMs}ms`);
        resolve(false);
        return;
      }
      setTimeout(probe, 400);
    };

    probe();
  });
}

async function ensureBackendStarted() {
  if (backendProcess && !backendProcess.killed) {
    return waitForHealth(4000);
  }

  const backendDataDir = getBackendDataDir();
  fs.mkdirSync(backendDataDir, { recursive: true });
  logLine(`starting backend, packaged=${app.isPackaged}`);

  const env = {
    ...process.env,
    QQPET_APP_DATA_DIR: backendDataDir,
    PYTHONUNBUFFERED: "1",
  };

  let childSpec = null;

  if (app.isPackaged) {
    const executable = getPackagedBackendExec();
    if (!executable) {
      logLine(`packaged executable not found under ${process.resourcesPath}`);
      return false;
    }
    try {
      fs.chmodSync(executable, 0o755);
      logLine(`ensured executable permission: ${executable}`);
    } catch (error) {
      logLine(`chmod failed for ${executable}: ${error.message}`);
    }
    childSpec = {
      command: executable,
      args: [],
      cwd: path.dirname(executable),
    };
  } else {
    childSpec = getDevBackendCommand();
  }

  if (!childSpec) {
    logLine("unable to determine backend command");
    return false;
  }

  logLine(`spawn command: ${childSpec.command} ${childSpec.args.join(" ")}`.trim());
  logLine(`spawn cwd: ${childSpec.cwd}`);
  stopping = false;
  backendProcess = spawn(childSpec.command, childSpec.args, {
    cwd: childSpec.cwd,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout?.on("data", (chunk) => {
    logLine(`stdout: ${String(chunk).trimEnd()}`);
    process.stdout.write(`[backend] ${chunk}`);
  });

  backendProcess.stderr?.on("data", (chunk) => {
    logLine(`stderr: ${String(chunk).trimEnd()}`);
    process.stderr.write(`[backend] ${chunk}`);
  });

  backendProcess.on("error", (error) => {
    logLine(`spawn error: ${error.message}`);
  });

  backendProcess.on("exit", (code, signal) => {
    if (!stopping) {
      logLine(`backend exited unexpectedly: code=${code} signal=${signal}`);
    }
    backendProcess = null;
  });

  return waitForHealth();
}

function stopBackend() {
  stopping = true;
  if (!backendProcess || backendProcess.killed) {
    backendProcess = null;
    return;
  }

  try {
    backendProcess.kill("SIGTERM");
  } catch (_) {}

  const pid = backendProcess.pid;
  setTimeout(() => {
    if (!backendProcess || backendProcess.killed || backendProcess.pid !== pid) {
      return;
    }
    try {
      backendProcess.kill("SIGKILL");
    } catch (_) {}
  }, 5000);
}

module.exports = {
  ensureBackendStarted,
  stopBackend,
  getBackendDataDir,
  getBackendLogPath,
};
