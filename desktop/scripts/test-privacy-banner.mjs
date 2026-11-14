import fs from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);
const source = fs.readFileSync(new URL("../src/components/PrivacyBanner.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const exports = {};
vm.runInNewContext(compiled, { exports, require });
for (const model of ["translategemma:4b", "translategemma:12b", "translategemma:27b", "nllb"]) {
  const html = renderToStaticMarkup(React.createElement(exports.PrivacyBanner, {
    settings: { translate_provider: model, tts_provider: "xtts-v2" },
  }));
  assert.match(html, /offline trên máy/);
  assert.doesNotMatch(html, /cần Internet/);
  const fallback = renderToStaticMarkup(React.createElement(exports.PrivacyBanner, {
    settings: { translate_provider: model, tts_provider: "xtts-v2", translate_fallback_online: true },
  }));
  assert.match(fallback, /Fallback Google được bật/);
  assert.doesNotMatch(fallback, /Chế độ offline: bản dịch và giọng đọc không rời máy/);
}
console.log("PrivacyBanner: four local providers and opt-in fallback passed");
