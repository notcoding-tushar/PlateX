import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const root = fileURLToPath(new URL("../", import.meta.url));
const python = join(root, ".venv", "Scripts", "python.exe");
const cloudflared = join(root, "external_tools", "cloudflare", "cloudflared.exe");
const vite = join(root, "frontend", "node_modules", "vite", "bin", "vite.js");
for (const path of [python, cloudflared, vite]) {
  if (!existsSync(path)) throw new Error(`Missing prerequisite: ${path}`);
}
if (spawnSync(cloudflared, ["--version"], { stdio: "ignore" }).status !== 0) {
  throw new Error("Cloudflare executable could not run. Download it again from Cloudflare's official downloads page.");
}

const children = new Set();
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) child.kill();
}
function start(command, args) {
  const child = spawn(command, args, { cwd: root, stdio: "inherit" });
  children.add(child);
  child.on("error", error => { console.error(error.message); stop(1); });
  child.on("exit", code => { children.delete(child); if (!stopping) stop(code || 1); });
  return child;
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());

const build = spawn(process.execPath, [vite, "build"], { cwd: join(root, "frontend"), stdio: "inherit" });
const code = await new Promise(resolve => { build.on("exit", resolve); build.on("error", () => resolve(1)); });
if (code !== 0) process.exit(1);
const probe = createServer();
await new Promise((resolve, reject) => {
  probe.once("error", reject);
  probe.listen(18573, "127.0.0.1", () => probe.close(resolve));
});
const app = "from api.main import app; from fastapi.staticfiles import StaticFiles; import uvicorn; app.mount('/', StaticFiles(directory='frontend/dist', html=True)); uvicorn.run(app, host='127.0.0.1', port=18573)";
start(python, ["-c", app]);
let ready = false;
for (let i = 0; i < 100 && !stopping; i++) {
  ready = await fetch("http://127.0.0.1:18573/api/health", { signal: AbortSignal.timeout(500) })
    .then(r => r.ok, () => false);
  if (ready) break;
  await delay(200);
}
if (!ready || stopping) {
  console.error("PlateX did not start on port 18573.");
  stop(1);
} else {
  console.log("Share the trycloudflare.com URL below. Press Ctrl+C to stop sharing.");
  start(cloudflared, ["tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:18573"]);
}
