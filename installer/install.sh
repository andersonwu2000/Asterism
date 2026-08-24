#!/usr/bin/env bash
# Asterism installer (macOS / Linux, incl. Ubuntu 24.04 ARM64 — Oracle
# Ampere A1). Run:  bash installer/install.sh [--fix-leantar]
# Idempotent — re-running skips finished steps. The Windows story
# ("Asterism.exe", repo root) is a separate, no-terminal
# flow.
#
# `--fix-leantar`: opt-in. If the Lean toolchain's bundled `leantar`
# binary turns out to be the WRONG architecture for this host (the
# known Lean 4.30.0-rc2 failure mode on aarch64 — see
# docs/internal/dev/oracle_arm64_cloud_readiness.md P0#1), this script
# always FAILS LOUDLY and prints the fix; only with this flag does it
# also fetch the correct-arch `leantar` from its own upstream
# (github.com/digama0/leangz, verified against its v0.1.19 release
# assets) and replace the binary in place. The Lean pin
# (`lean-toolchain`) is never touched by either path.
#
# Sourceable for testing: every step lives in a function, and `main`
# only runs when this file is EXECUTED, not sourced (the
# BASH_SOURCE/$0 guard at the bottom) — `tests/test_installer_install_sh.py`
# sources it and calls the pure classify_*/enabled_providers functions
# directly, with fake `uname`/`file`/`elan` on PATH, so the architecture
# and provider-selection logic is covered without a real Lean/Node
# install or a real Oracle box.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
#: step_python (below) picks the real interpreter and overwrites this;
#: the default lets a SOURCED script (tests) call provider_json_get
#: without running the full step sequence first.
PY="${PY:-python3}"

#: The leantar release that fixes the rc2 ARM64 mis-packaging, and
#: where it lives. Verified 2026-08-24 against the live GitHub API
#: (mathlib's own Cache/README.md points at this repo — the tool is
#: named "leantar" but the REPO is "leangz"):
#:   GET https://api.github.com/repos/digama0/leangz/releases/tags/v0.1.19
#:   -> assets include leantar-v0.1.19-aarch64-unknown-linux-musl.tar.gz
#:      and leantar-v0.1.19-x86_64-unknown-linux-musl.tar.gz
LEANTAR_FIX_VERSION="0.1.19"
LEANTAR_REPO="digama0/leangz"

FIX_LEANTAR=0
for _arg in "$@"; do
  case "$_arg" in
    --fix-leantar) FIX_LEANTAR=1 ;;
  esac
done

TOTAL_STEPS=8
step() { printf '\n\033[36m[%s/%s] %s\033[0m\n' "$1" "$TOTAL_STEPS" "$2"; }
ok()   { printf '   \033[32mOK\033[0m   %s\n' "$1"; }
note() { printf '        %s\n' "$1"; }
fail() { printf '   \033[31mFAIL\033[0m %s\n' "$1"; }

# --------------------------------------------------------- architecture

# Normalizes `uname -m` (or any machine string) to the two families the
# rest of this script cares about. Mirrors
# Tooling/core/cloud_doctor.py::classify_host_arch exactly — installer
# and `asterism doctor --cloud` must agree, or one could pass while the
# other fails on the identical machine.
classify_host_arch() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    aarch64|arm64) echo aarch64 ;;
    x86_64|amd64|x64) echo x86_64 ;;
    *) echo unknown ;;
  esac
}

# Classifies a `file <binary>` text report the same way
# cloud_doctor.py::classify_elf_arch does: `file`'s own wording is "ARM
# aarch64" / "x86-64" (hyphen, not underscore).
classify_elf_arch() {
  local low
  low="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$low" in
    *aarch64*|*arm64*) echo aarch64 ;;
    *x86-64*|*x86_64*) echo x86_64 ;;
    *) echo unknown ;;
  esac
}

step_arch() {
  step 1 "CPU architecture…"
  local machine arch
  machine="$(uname -m)"
  arch="$(classify_host_arch "$machine")"
  note "uname -m: $machine (class: $arch)"
  if [ "$arch" = unknown ]; then
    note "unrecognized architecture family — continuing without assuming x86-64; the leantar architecture check later in this script will SKIP rather than guess"
  fi
  ok "architecture detected, no assumption silently made"
}

# --------------------------------------------------------- system deps

step_system_deps() {
  step 2 "System dependencies (git, curl, tar, unzip, zstd, Node.js)…"
  local missing=0 c
  for c in git curl tar unzip zstd; do
    if command -v "$c" >/dev/null; then
      ok "$c"
    else
      note "$c missing — install it via your package manager (Ubuntu: sudo apt-get install -y $c), then re-run."
      missing=1
    fi
  done
  if command -v npm >/dev/null; then
    ok "npm $(npm --version 2>/dev/null || echo '?')"
  else
    note "npm missing — install Node.js LTS (https://nodejs.org, or on Ubuntu: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs), then re-run."
    missing=1
  fi
  if [ "$missing" = 1 ]; then
    note "install the missing tool(s) above and re-run — nothing later in this script can substitute for them."
    exit 1
  fi
}

# --------------------------------------------------------- python / engine / web

step_python() {
  step 3 "Python 3.12+…"
  PY=python3
  if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
    if command -v python3.12 >/dev/null; then PY=python3.12
    else
      note "Install Python 3.12 first (macOS: brew install python@3.12 / Ubuntu: sudo apt-get install -y python3.12 python3.12-venv), then re-run."
      exit 1
    fi
  fi
  ok "$($PY -V)"
}

step_engine() {
  step 4 "The Asterism engine (Python packages)…"
  "$PY" -m pip install -e "$ROOT" --quiet --disable-pip-version-check
  ok "engine installed"
}

step_web() {
  step 5 "The web interface…"
  if [ -f "$ROOT/web/dist/index.html" ]; then
    ok "a built interface is already present"
  else
    (cd "$ROOT/web" && npm ci --no-audit --no-fund && npm run build)
    ok "interface built"
  fi
}

# --------------------------------------------------------- lean / leantar

# Fetches the correct-arch leantar release asset and replaces the
# binary at $1 (the path `elan which leantar` reported). Only called
# under --fix-leantar, after the loud mismatch report has already
# printed — this is the MUTATION half, kept separate from detection so
# a plain `bash install.sh` never silently rewrites a binary.
fetch_and_replace_leantar() {
  local target_path="$1" host="$2"
  local url="https://github.com/${LEANTAR_REPO}/releases/download/v${LEANTAR_FIX_VERSION}/leantar-v${LEANTAR_FIX_VERSION}-${host}-unknown-linux-musl.tar.gz"
  local tmp
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064 — tmp is fixed at trap-set time, intentional
  trap "rm -rf '$tmp'" RETURN
  note "downloading $url"
  curl -sSfL "$url" -o "$tmp/leantar.tar.gz"
  tar xzf "$tmp/leantar.tar.gz" -C "$tmp"
  local fetched
  fetched="$(find "$tmp" -maxdepth 2 -type f -name 'leantar*' ! -name '*.tar.gz' | head -n1)"
  if [ -z "$fetched" ]; then
    fail "the downloaded archive did not contain a leantar binary — aborting the replace, toolchain left as-is"
    exit 1
  fi
  cp "$target_path" "${target_path}.bak-$(date +%s)"
  chmod +x "$fetched"
  cp "$fetched" "$target_path"
  local recheck
  recheck="$(classify_elf_arch "$(file "$target_path" 2>/dev/null || true)")"
  if [ "$recheck" != "$host" ]; then
    fail "replaced $target_path but it still does not classify as $host — investigate manually (backup kept alongside it)"
    exit 1
  fi
  ok "replaced $target_path with the $host build (backup kept alongside it)"
}

# Detection half: elan which leantar -> file -> compare against the
# host. FAILS LOUDLY on a mismatch (never a silent x86-64-on-ARM64), and
# only touches the binary when --fix-leantar was passed. Never touches
# lean-toolchain.
check_leantar_arch() {
  local leantar_path
  leantar_path="$(elan which leantar 2>/dev/null || true)"
  if [ -z "$leantar_path" ]; then
    note "leantar not yet resolved by elan — will be verified again after 'lake exe cache get' triggers the toolchain install; re-run 'asterism doctor --cloud' afterwards if that step fails with an exec-format error"
    return 0
  fi
  local file_out observed host
  file_out="$(file "$leantar_path" 2>/dev/null || true)"
  observed="$(classify_elf_arch "$file_out")"
  host="$(classify_host_arch "$(uname -m)")"
  if [ "$observed" = unknown ] || [ "$host" = unknown ]; then
    note "could not classify leantar's architecture from \`file\` output ($file_out) — proceeding, but watch 'lake exe cache get' for an exec-format error"
    return 0
  fi
  if [ "$observed" = "$host" ]; then
    ok "leantar ($leantar_path) matches host arch $host"
    return 0
  fi
  fail "leantar architecture mismatch: $leantar_path is $observed ELF but this host is $host"
  note "lake exe cache get / lake build WILL fail with an exec-format error until this is fixed."
  note "fix: fetch leantar-v${LEANTAR_FIX_VERSION}-${host}-unknown-linux-musl from https://github.com/${LEANTAR_REPO}/releases and replace the binary at $leantar_path"
  note "     (the Lean pin in lean-toolchain is NOT touched by this fix — only the leantar helper binary)"
  if [ "$FIX_LEANTAR" = 1 ]; then
    note "--fix-leantar was passed — fetching the correct build now…"
    fetch_and_replace_leantar "$leantar_path" "$host"
  else
    note "re-run with --fix-leantar to fetch and replace it automatically, or do it by hand."
    exit 1
  fi
}

step_lean() {
  step 6 "The Lean theorem prover…"
  if ! command -v lake >/dev/null; then
    note "Installing elan (the Lean toolchain manager)…"
    curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y
    export PATH="$HOME/.elan/bin:$PATH"
  fi
  # Materializes the pinned toolchain (reads ./lean-toolchain) without
  # yet downloading the multi-GB Mathlib cache — this is what makes
  # `elan which leantar` resolvable for the check right after it.
  (cd "$ROOT" && lake --version >/dev/null)
  check_leantar_arch
  note "Fetching the prebuilt math library (Mathlib) — several GB the first time."
  (cd "$ROOT" && lake exe cache get)
  ok "math library ready"
}

# --------------------------------------------------------- providers

# Every provider actually seated on a pipeline kind, read from
# Asterism.yaml the same way the work order sanctions ("grep for
# provider: values is fine") — plus 'claude', always, because an
# UNLISTED kind falls back to claude by config.py's own default
# (Tooling/core/config.py get(..., default="claude")), so grep alone
# would silently miss a claude-only seat that never wrote its own line.
enabled_providers() {
  {
    echo claude
    if [ -f "$ROOT/Asterism.yaml" ]; then
      # `|| true`: grep exits 1 on ZERO matches (a yaml with every
      # provider: line commented out, or none at all), which under
      # `set -eo pipefail` would otherwise abort this function — "no
      # explicit provider lines" is a normal, expected shape (config.py
      # defaults every unlisted kind to claude), not an error.
      grep -E '^[[:space:]]*provider:[[:space:]]*[A-Za-z0-9_]+' "$ROOT/Asterism.yaml" \
        | sed -E 's/^[[:space:]]*provider:[[:space:]]*([A-Za-z0-9_]+).*/\1/' \
        || true
    fi
  } | sort -u
}

# Pulls one field out of the JSON `installer/provider-info.py` prints —
# the seam that keeps this script from inventing its own idea of a
# provider's install/auth story (Tooling/llm/capabilities.py owns the
# declaration; setup-orchestrator.ps1 uses the same script on Windows).
provider_json_get() {  # $1=json  $2=field name
  printf '%s' "$1" | "$PY" -c "
import json, sys
d = json.load(sys.stdin)
v = d.get('$2')
print('' if v is None else v)
"
}

# The ONE deliberate branch-by-name in this script: `install_command`
# in capabilities.py is a POWERSHELL one-liner (setup-orchestrator.ps1's
# own seam), not bash-executable, so it cannot be eval'd here. claude
# and codex/zen both resolve to a plain `npm install -g <pkg>` on every
# platform, which is safe to hardcode; every OTHER provider falls
# through to "set it up yourself", read from the DECLARED
# install_method rather than guessed from its name.
install_provider_cli() {  # $1=provider name
  case "$1" in
    claude) npm install -g @anthropic-ai/claude-code ;;
    codex|zen) npm install -g @openai/codex ;;
    *) return 1 ;;
  esac
}

step_providers() {
  step 7 "Agent provider CLIs (from Asterism.yaml)…"
  local providers prov info installed install_method exe auth_flow env_key
  providers="$(enabled_providers)"
  note "enabled providers: $(printf '%s' "$providers" | tr '\n' ' ')"
  for prov in $providers; do
    info="$("$PY" "$ROOT/installer/provider-info.py" "$prov" --check 2>/dev/null || true)"
    if [ -z "$info" ]; then
      note "$prov: could not query provider-info.py — skipping"
      continue
    fi
    installed="$(provider_json_get "$info" installed)"
    install_method="$(provider_json_get "$info" install_method)"
    exe="$(provider_json_get "$info" exe)"
    if [ "$installed" = True ]; then
      ok "$prov already installed ($exe)"
    else
      if install_provider_cli "$prov"; then
        info="$("$PY" "$ROOT/installer/provider-info.py" "$prov" --check 2>/dev/null || true)"
        installed="$(provider_json_get "$info" installed)"
        if [ "$installed" = True ]; then ok "$prov installed"
        else note "$prov: still not found after 'npm install' — check the output above"
        fi
      else
        note "$prov: install_method=$install_method — no automated Linux/macOS install for this one; set it up yourself, then re-run"
        continue
      fi
    fi

    auth_flow="$(provider_json_get "$info" auth_flow)"
    env_key="$(provider_json_get "$info" env_key)"
    case "$prov" in
      claude)
        if [ -f "$HOME/.claude/.credentials.json" ]; then
          ok "claude: logged in"
        else
          note "claude: one-time login — run 'claude' in a terminal on THIS machine and follow the prompts (credentials are per-machine; never copy .credentials.json from Windows)."
        fi
        ;;
      codex)
        note "codex: one-time login — run 'codex login' in a terminal on THIS machine (uses your ChatGPT/OpenAI account)."
        ;;
      zen)
        note "zen rides the SAME 'codex' binary but authenticates via an API key (OPENROUTER_API_KEY in .env), never via 'codex login' — do NOT sign the shared codex CLI into a ChatGPT account for the zen seat, that changes its credential source and breaks zen spawns. Set OPENROUTER_API_KEY in $ROOT/.env."
        ;;
      *)
        if [ -n "$env_key" ]; then
          note "$prov: set $env_key in $ROOT/.env"
        elif [ "$auth_flow" = own_oauth ] || [ "$auth_flow" = borrowed_session ]; then
          note "$prov: sign in with its own CLI/IDE yourself, then re-run"
        fi
        ;;
    esac
  done
}

step_done() {
  step 8 "Done."
  note "Start the console with:   cd '$ROOT' && asterism serve"
  note "then open http://127.0.0.1:8642 in your browser."
  note "Cloud readiness check:    asterism doctor --cloud"
}

main() {
  step_arch
  step_system_deps
  step_python
  step_engine
  step_web
  step_lean
  step_providers
  step_done
}

# Run only when EXECUTED (`bash install.sh`), not when sourced — the
# test suite sources this file to exercise classify_host_arch /
# classify_elf_arch / enabled_providers / provider_json_get directly.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
