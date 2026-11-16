// Start `python -m dipm serve <design>` for a test, on a free port, from the repo's .venv.
import { spawn, type ChildProcess } from "node:child_process";
import { cpSync, existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const ROOT = resolve(here, "../..");
export const PY = join(ROOT, ".venv/bin/python");
let nextPort = 8800 + Math.floor(Math.random() * 100);

export interface Server { url: string; proc: ChildProcess; dir: string; design: string; stop: () => void }

/** Copy a design (and its lock) to a fresh temp dir so tests may write prefs/locks or edit it. */
export function copyDesign(rel: string): string {
  const src = join(ROOT, rel);
  const dir = mkdtempSync(join(tmpdir(), "dipm-e2e-"));
  cpSync(src, join(dir, basename(src)));
  // the design set: lock, intent file, review record (iteration 2)
  for (const suffix of [".interpretations.json", ".intent.yaml", ".review.json", ".resolution.json"]) {
    const f = src.replace(/\.py$/, suffix);
    if (existsSync(f)) cpSync(f, join(dir, basename(f)));
  }
  return join(dir, basename(src));
}

/** The stub `claude` (tests/fixtures/fake_claude): e2e tests never start the real one. */
export const FAKE_CLAUDE = join(ROOT, "tests/fixtures/fake_claude");

export async function startServer(design: string, env: Record<string, string> = {}): Promise<Server> {
  const port = nextPort++;
  // iteration 4b: no test may start the real `claude`; specs opt in to the stub via `env`
  const safe = { DIPM_CLAUDE_BIN: "/nonexistent/claude-is-disabled-in-tests", DIPM_CLAUDE_AUTORUN: "0" };
  const proc = spawn(PY, ["-m", "dipm", "serve", design, "--no-open", "--port", String(port)], {
    cwd: ROOT, stdio: ["ignore", "pipe", "pipe"], env: { ...process.env, ...safe, ...env },
  });
  let out = "";
  proc.stdout!.on("data", (d) => (out += d));
  proc.stderr!.on("data", (d) => (out += d));
  for (let i = 0; i < 120; i++) {
    const m = /at (http:\/\/127\.0\.0\.1:\d+\/)/.exec(out); // the port actually bound
    if (m) {
      try {
        const r = await fetch(m[1] + "api/design");
        if (r.ok) return { url: m[1], proc, dir: dirname(design), design, stop: () => proc.kill() };
      } catch { /* not up yet */ }
    }
    await new Promise((r) => setTimeout(r, 150));
  }
  proc.kill();
  throw new Error(`dipm serve did not start:\n${out}`);
}
