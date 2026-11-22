import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const root = fileURLToPath(new URL("../", import.meta.url));
const frontend = join(root, "frontend");
const vite = join(frontend, "node_modules", "vite", "bin", "vite.js");
const windows = process.platform === "win32";
const localPython = windows
  ? join(root, ".venv", "Scripts", "python.exe")
  : join(root, ".venv", "bin", "python");
const python = process.env.PLATEX_PYTHON ||
  (existsSync(localPython) ? localPython : windows ? "python" : "python3");
const children = new Set();
let stopping = false;

function stop(code) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) child.kill();
}

function start(name, command, args, cwd) {
  const child = spawn(command, args, { cwd, stdio: "inherit" });
  children.add(child);
  child.once("error", (error) => {
    children.delete(child);
    console.error(`Could not start ${name}: ${error.message}`);
    stop(1);
  });
  child.once("exit", (code, signal) => {
    children.delete(child);
    if (stopping) return;
    console.error(`${name} stopped (${signal ?? code}).`);
    stop(code || 1);
  });
}

process.once("SIGINT", () => stop(0));
process.once("SIGTERM", () => stop(0));

if (!existsSync(vite)) {
  console.error("Install frontend dependencies with npm ci --prefix frontend.");
  stop(1);
} else {
  start("FastAPI", python, ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
    join(root, "backend"));
  // The workbench requests a solve on page load, so start Vite after the API is ready.
  const deadline = Date.now() + 30_000;
  while (!stopping && Date.now() < deadline) {
    const health = await fetch("http://127.0.0.1:8000/api/health", {
      signal: AbortSignal.timeout(500),
    }).then((response) => response.ok, () => false);
    if (health && !stopping) {
      start("Vite", process.execPath, [vite, "--host", "127.0.0.1"], frontend);
      break;
    }
    if (!stopping) await delay(150);
  }
  if (!stopping && children.size === 1) {
    console.error("FastAPI did not become ready within 30 seconds.");
    stop(1);
  }
}
