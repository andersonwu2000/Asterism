# The editor of files mode

The code editor of files mode is CodeMirror 6, bundled once into `asterism/static/vendor/codemirror/codemirror.min.js`
(one minified file, one global `CodeMirror`) with the licences of everything in it beside it
(`asterism/static/vendor/codemirror/LICENSE`). The server and its deployment have no build step: the bundle is
committed. This folder is the recipe that produced it.

- `package.json` — the packages, each at an exact version; `package-lock.json` — every package that is downloaded,
  with its integrity hash (npm refuses a tarball that does not match).
- `entry.mjs` — what the pages use of CodeMirror; only that ends up in the bundle.
- `build.mjs` — runs esbuild and writes the licence file from esbuild's record of which packages are in the bundle.

## Rebuilding

From this folder, with Node.js and npm:

    npm ci --ignore-scripts
    npm run build

`npm ci` downloads exactly what the lock file names, from registry.npmjs.org, and runs no install scripts (esbuild's
binary comes as a platform package and needs none). The build replaces everything in
`asterism/static/vendor/codemirror/`. What it downloads (`node_modules/`) is ignored by git.

To move to newer versions: change the exact versions in `package.json`, run `npm install --ignore-scripts`, rebuild,
and update the entry in `asterism/static/vendor/README`.
