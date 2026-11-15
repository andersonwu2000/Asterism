// Builds entry.mjs into one minified IIFE with the global `CodeMirror`, and writes beside it one LICENSE file that
// names every package whose code is in the bundle (taken from esbuild's own record of what it wrote) with its licence.
// Run with `npm run build` after `npm ci --ignore-scripts` (see README.md).
import { build } from "esbuild";
import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, "../../asterism/static/vendor/codemirror");
const file = "codemirror.min.js";

mkdirSync(out, { recursive: true });
for (const old of readdirSync(out)) rmSync(join(out, old));

const result = await build({
  entryPoints: [join(here, "entry.mjs")],
  bundle: true,
  minify: true,
  format: "iife",
  globalName: "CodeMirror",
  target: ["chrome109", "edge109", "firefox115", "safari16"],
  charset: "utf8",
  legalComments: "none",
  metafile: true,
  outfile: join(out, file),
  logLevel: "info",
});

// node_modules/<name> or node_modules/@scope/<name>, for every input that left code in the bundle (what was read
// and then shaken out entirely is not in it).
const packages = new Map();
const bundled = Object.values(result.metafile.outputs)[0].inputs;
for (const input of Object.keys(bundled).filter((k) => bundled[k].bytesInOutput > 0)) {
  const m = /node_modules\/((?:@[^/]+\/)?[^/]+)\//.exec(input.replace(/\\/g, "/"));
  if (!m) continue;
  const dir = join(here, "node_modules", m[1]);
  const manifest = JSON.parse(readFileSync(join(dir, "package.json"), "utf8"));
  const licence = readdirSync(dir).find((f) => /^licen[cs]e/i.test(f));
  if (!licence) throw new Error(`${m[1]} has no licence file`);
  packages.set(m[1], { version: manifest.version, licence: manifest.license, text: readFileSync(join(dir, licence), "utf8").trim() });
}
const names = [...packages.keys()].sort();
const parts = [`${file} bundles these packages (from the npm registry, unmodified; built by tools/editor):`, ""];
for (const n of names) parts.push(`  ${n} ${packages.get(n).version} (${packages.get(n).licence})`);
for (const n of names) parts.push("", "-".repeat(78), `${n} ${packages.get(n).version}`, "", packages.get(n).text);
writeFileSync(join(out, "LICENSE"), parts.join("\n") + "\n");

const code = readFileSync(join(out, file), "utf8");
for (const bad of [/\beval\(/, /new Function\(/, /\bimport\(/]) {
  if (bad.test(code)) throw new Error(`the bundle contains ${bad}`);
}
console.log(`${file}: ${code.length} bytes; ${names.length} packages: ${names.join(", ")}`);
