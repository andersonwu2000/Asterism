#!/usr/bin/env bash
# Asterism installer (macOS / Linux). Run:  bash installer/install.sh
# Idempotent — re-running skips finished steps. The Windows story
# ("Setup Asterism.exe", next to this file) is a separate, no-terminal
# flow.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
step() { printf '\n\033[36m[%s/6] %s\033[0m\n' "$1" "$2"; }
ok()   { printf '   \033[32mOK\033[0m   %s\n' "$1"; }
note() { printf '        %s\n' "$1"; }

step 1 "Python 3.12+…"
PY=python3
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
  if command -v python3.12 >/dev/null; then PY=python3.12
  else
    note "Install Python 3.12 first (macOS: brew install python@3.12 / Linux: your package manager), then re-run."
    exit 1
  fi
fi
ok "$($PY -V)"

step 2 "The Asterism engine (Python packages)…"
"$PY" -m pip install -e "$ROOT" --quiet --disable-pip-version-check
ok "engine installed"

step 3 "The web interface…"
if [ -f "$ROOT/web/dist/index.html" ]; then
  ok "a built interface is already present"
else
  command -v npm >/dev/null || { note "Install Node.js LTS (https://nodejs.org), then re-run."; exit 1; }
  (cd "$ROOT/web" && npm ci --no-audit --no-fund && npm run build)
  ok "interface built"
fi

step 4 "The Lean theorem prover…"
if ! command -v lake >/dev/null; then
  note "Installing elan (the Lean toolchain manager)…"
  curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y
  export PATH="$HOME/.elan/bin:$PATH"
fi
note "Fetching the prebuilt math library (Mathlib) — several GB the first time."
(cd "$ROOT" && lake exe cache get)
ok "math library ready"

step 5 "Claude Code (the AI that writes the proofs)…"
if ! command -v claude >/dev/null; then
  command -v npm >/dev/null || { note "Install Node.js LTS first."; exit 1; }
  npm install -g @anthropic-ai/claude-code
fi
if [ -f "$HOME/.claude/.credentials.json" ]; then
  ok "installed and logged in"
else
  note "One-time login with your Claude subscription: run 'claude' in a terminal and follow the prompts."
fi

step 6 "Done."
note "Start the console with:   cd '$ROOT' && asterism serve"
note "then open http://127.0.0.1:8642 in your browser."
