import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8");
function client({ env = {}, savedSession = null, blockedStorage = false, offline = false } = {}) {
  const calls = [];
  const values = new Map(savedSession ? [["session_id", savedSession]] : []);
  const context = {
    exports: {}, env,
    crypto: { randomUUID: () => "new-session" },
    localStorage: {
      getItem: (key) => { if (blockedStorage) throw Error("blocked"); return values.get(key) ?? null; },
      setItem: (key, value) => { if (blockedStorage) throw Error("blocked"); values.set(key, value); },
    },
    AbortSignal: { timeout: (ms) => ({ timeout: ms }) },
    fetch: async (url, options) => {
      calls.push({ url, options });
      if (offline) throw Error("offline");
      return { ok: true, json: async () => ({ status: "READY" }) };
    },
  };
  const js = ts.transpileModule(source.replaceAll("import.meta.env", "env"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(js, context);
  return { ...context.exports, calls, values };
}

test("production chat and research share the persisted session and same-origin API", async () => {
  const c = client({ savedSession: "returning-member" });
  await c.api.agent("I need a crown");
  await c.api.runResearch();
  await c.api.research();
  assert.deepEqual(JSON.parse(c.calls[0].options.body), { message: "I need a crown", session_id: "returning-member" });
  assert.equal(c.calls[0].url, "/api/v1/agent/message");
  assert.equal(c.calls[0].options.signal.timeout, 30000);
  assert.equal(c.calls[1].url, "/api/v1/research/returning-member/run");
  assert.equal(c.calls[1].options.method, "POST");
  assert.equal(c.calls[1].options.keepalive, true);
  assert.equal(c.calls[2].url, "/api/v1/research/returning-member");
});

test("development and explicit API origins remain supported", () => {
  assert.equal(client({ env: { DEV: true } }).API_BASE, "http://localhost:8000");
  assert.equal(client({ env: { VITE_API_BASE: "https://api.example.test" } }).API_BASE, "https://api.example.test");
  assert.equal(client({ env: { DEV: true, VITE_API_BASE: "" } }).API_BASE, "");
});

test("new sessions persist and blocked storage still supports chat and research", async () => {
  assert.equal(client().values.get("session_id"), "new-session");
  const c = client({ blockedStorage: true });
  await c.api.agent("cleaning");
  await c.api.research();
  assert.equal(JSON.parse(c.calls[0].options.body).session_id, "new-session");
  assert.equal(c.calls[1].url, "/api/v1/research/new-session");
});

test("unavailable backend preserves graceful fallback for chat and research", async () => {
  const c = client({ offline: true });
  assert.equal(await c.api.agent("cleaning"), null);
  assert.equal(await c.api.research(), null);
  assert.equal(await c.api.runResearch(), null);
});
