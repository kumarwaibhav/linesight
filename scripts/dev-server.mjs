// Start the local API and Vite frontend together so one command launches the full workspace.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve, delimiter } from "node:path";

const runtimePython = process.env.CODEX_PRIMARY_RUNTIME_PYTHON;
const managedPython = "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3";
const localPython = process.platform === "win32" ? resolve(".venv/Scripts/python.exe") : resolve(".venv/bin/python");
const python = existsSync(localPython) ? localPython : runtimePython || (existsSync(managedPython) ? managedPython : process.platform === "win32" ? "python" : "python3");
const env = { ...process.env };
if (existsSync(".preview-deps")) env.PYTHONPATH = [resolve(".preview-deps"), env.PYTHONPATH].filter(Boolean).join(delimiter);

const api = spawn(python, ["scripts/serve.py", "--host", "127.0.0.1", "--port", "8000"], { stdio: "inherit", env });
const vite = spawn(process.execPath, [resolve("node_modules/vite/bin/vite.js"), "--host", "0.0.0.0", "--port", "4173", "--strictPort"], { stdio: "inherit", env });
const children = [api, vite];
let stopping = false;

function stop(signal = "SIGTERM") {
  if (stopping) return;
  stopping = true;
  for (const child of children) if (child.exitCode === null) child.kill(signal);
}

for (const child of children) {
  child.on("error", (error) => { console.error(error.message); stop(); process.exitCode = 1; });
  child.on("exit", (code) => {
    if (!stopping) {
      process.exitCode = code ?? 1;
      stop();
    }
  });
}
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => stop(signal));
