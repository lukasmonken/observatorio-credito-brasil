import { build } from "esbuild";
import { readFile, writeFile, mkdir, rm, copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = path.dirname(fileURLToPath(import.meta.url));
const dist = path.join(root, "dist");
const config = JSON.parse(
  await readFile(path.join(root, "generated/site.json"), "utf8"),
);
if (!/^data-[a-f0-9]{16}\.json$/.test(config.data))
  throw new Error("Nome de dados inválido");
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });
const result = await build({
  absWorkingDir: root,
  entryPoints: ["src/app.js"],
  outdir: "dist/assets",
  entryNames: "[name]-[hash]",
  chunkNames: "[name]-[hash]",
  bundle: true,
  splitting: true,
  format: "esm",
  minify: true,
  metafile: true,
  target: ["es2022"],
  legalComments: "linked",
});
const entry = Object.entries(result.metafile.outputs).find(
  ([, v]) => v.entryPoint === "src/app.js",
);
const js = path.relative("dist", entry[0]),
  css = path.relative("dist", entry[1].cssBundle);
const html = (await readFile(path.join(root, "index.html"), "utf8"))
  .replace("{{JS}}", js)
  .replace("{{CSS}}", css);
await writeFile(path.join(dist, "index.html"), html);
await writeFile(path.join(dist, ".nojekyll"), "");
for (const name of ["site.json", config.data])
  await copyFile(path.join(root, "generated", name), path.join(dist, name));
console.log(`Site gerado: ${dist}`);
