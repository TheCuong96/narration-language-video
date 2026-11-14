import fs from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
import ts from "typescript";

const source = fs.readFileSync(new URL("../src/lib/engine.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
let listener;
let removed = 0;
let spawned = 0;
const exports = {};
vm.runInNewContext(compiled, {
  exports,
  window: { __TAURI_INTERNALS__: {} },
  require(name) {
    if (name === "@tauri-apps/api/event") return {
      listen: async (_, callback) => { listener = callback; return () => { removed++; }; },
    };
    if (name === "@tauri-apps/api/core") return {
      invoke: async () => { spawned++; return "spawned"; },
    };
    throw new Error(`Unexpected import: ${name}`);
  },
});
const tick = () => new Promise((resolve) => setImmediate(resolve));
const events = [];
let completed = false;
const download = exports.downloadModel("translategemma:4b", (ev) => events.push(ev))
  .then(() => { completed = true; });
await tick();
assert.equal(spawned, 1);
assert.equal(completed, false);
assert.equal(removed, 0);
listener({ payload: { type: "progress", stage: "downloading_model", percent: 50 } });
assert.equal(events.at(-1).percent, 50);
listener({ payload: { type: "completed", model: "translategemma:12b" } });
await tick();
assert.equal(completed, false);
listener({ payload: { type: "completed", model: "translategemma:4b" } });
await download;
assert.equal(completed, true);
assert.equal(removed, 1);
const failed = exports.downloadModel("translategemma:4b");
await tick();
listener({ payload: { type: "error", fatal: true, message: "Ollama lỗi" } });
await assert.rejects(failed, /Ollama lỗi/);
assert.equal(removed, 2);
console.log("Model download: spawn/progress/completion/error lifecycle passed");
