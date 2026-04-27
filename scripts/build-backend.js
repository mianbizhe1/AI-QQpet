const { spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname, "..");
const scriptPath = path.join(root, "scripts", "build_python_backend.py");
const commands = process.platform === "win32" ? ["py", "python"] : ["python3", "python"];

let lastError = null;

for (const command of commands) {
  const result = spawnSync(command, [scriptPath], {
    cwd: root,
    stdio: "inherit",
  });

  if (!result.error && result.status === 0) {
    process.exit(0);
  }

  lastError = result.error || new Error(`${command} exited with code ${result.status}`);
}

console.error("[build-backend] failed to build Python backend");
if (lastError) {
  console.error(lastError.message);
}
process.exit(1);
