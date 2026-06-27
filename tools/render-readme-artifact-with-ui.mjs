#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function arg(name) {
  const idx = process.argv.indexOf(name);
  if (idx === -1 || idx + 1 >= process.argv.length) throw new Error(`missing ${name}`);
  return process.argv[idx + 1];
}

function firstExisting(paths) {
  for (const candidate of paths) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error(`ui renderer entrypoint not found: ${paths.join(", ")}`);
}

const modelPath = arg("--model");
const outDir = arg("--out");
const uiLibSrc = process.env.UI_LIB_SRC;
if (!uiLibSrc) throw new Error("UI_LIB_SRC is required");

const uiEntrypoint = firstExisting([
  path.join(uiLibSrc, "packages", "core-port", "src", "index.mjs"),
  path.join(uiLibSrc, "src", "index.mjs"),
]);
const mod = await import(pathToFileURL(uiEntrypoint).href);
const model = JSON.parse(fs.readFileSync(modelPath, "utf8"));
const result = mod.renderMarkdownDocument({ model });
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "README.md"), result.markdown);
fs.writeFileSync(path.join(outDir, "render-result.json"), JSON.stringify(result, null, 2) + "\n");
fs.writeFileSync(path.join(outDir, "render-diagnostics.jsonl"), result.diagnostics.map((row) => JSON.stringify(row)).join("\n") + (result.diagnostics.length ? "\n" : ""));
if (!result.ok) process.exit(1);
