"""Loogle wrapper: type-pattern search over Mathlib via HTTPS API.

Loogle (https://loogle.lean-lang.org/) is the Lean community's
type-pattern search service. Agents call it when they know the
*shape* of a lemma they need but not the name — complementing plain
Grep which handles keyword/name search.

Agent-facing entry point (invoked through the restricted Bash tool):

    python -m Tooling.knowledge.loogle 'Nat.factorial _ = _'
    python -m Tooling.knowledge.loogle '?p.Prime → ∏ _ ∈ _, _ = -1'

Output format: top-K matches, one per line:
    <name>  ::  <type>  [<module>]

`header` line preserved so agent sees Loogle's parse hint when 0
matches. On network failure: prints diagnosis to stderr, rc=1 so
the agent can fall back to Grep or decline.

Why a CLI shim rather than a Python tool the agent calls directly:
the claude CLI's `--allowed-tools "Bash(python -m Tooling.knowledge.loogle*)"`
restriction whitelists exactly this command pattern. Other Bash
calls remain blocked — agent can't accidentally `rm -rf` or curl
arbitrary URLs.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


LOOGLE_URL = "https://loogle.lean-lang.org/json"
DEFAULT_TIMEOUT_SEC = 30   # loogle responds in 1-3s; 30s is generous
DEFAULT_LIMIT = 15          # cap displayed hits to keep prompt small
MAX_LIMIT = 50              # hard ceiling so a misspecified --limit can't dump all


def query(pattern: str, *, timeout: int = DEFAULT_TIMEOUT_SEC,
          limit: int = DEFAULT_LIMIT) -> tuple[int, str]:
    """Call Loogle, return (rc, formatted_text). rc=0 even on 0 hits
    (a valid answer; agent should refine the pattern). rc=1 only on
    network / parse failure."""
    limit = max(1, min(limit, MAX_LIMIT))
    url = f"{LOOGLE_URL}?q={urllib.parse.quote(pattern)}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Asterism (lemma-search)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        data = json.loads(raw)
    except urllib.error.HTTPError as e:
        return 1, f"loogle HTTP error {e.code}: {e.reason}"
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        return 1, f"loogle network error: {e}"
    except (json.JSONDecodeError, ValueError) as e:
        return 1, f"loogle parse error: {e}"

    return 0, _format(data, limit=limit)


def _format(data: dict, *, limit: int) -> str:
    header = (data.get("header") or "").strip()
    hits = data.get("hits") or []
    count = data.get("count")
    out: list[str] = []
    if header:
        # Header may span multiple lines and is verbose; keep it but
        # collapse trailing whitespace so the formatted output is tight.
        out.append(header)
    if not hits:
        out.append("(no hits — try a less specific or different pattern)")
        return "\n".join(out)
    out.append(f"--- showing {min(limit, len(hits))} of {count} hits ---")
    for h in hits[:limit]:
        name = h.get("name", "?")
        typ = (h.get("type") or "").strip()
        # Loogle's type field often starts with ": " — trim for compactness
        if typ.startswith(":"):
            typ = typ.lstrip(":").strip()
        module = h.get("module", "?")
        # Single-line per hit; agent reads this top-down
        out.append(f"{name}  ::  {typ}  [{module}]")
    return "\n".join(out)


def _ensure_utf8_stdout() -> None:
    """Lean / Mathlib types contain unicode (∀ ∏ ℕ ←). Windows
    consoles default to cp950 / cp1252 which can't encode them — the
    write would raise UnicodeEncodeError and the agent sees a useless
    traceback. Force UTF-8 reconfigure when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # already UTF-8 or unsupported wrapper


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdout()
    p = argparse.ArgumentParser(
        prog="python -m Tooling.knowledge.loogle",
        description="Loogle type-pattern search over Mathlib.",
    )
    p.add_argument("pattern", help="Loogle query (type pattern)")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                   help=f"Max hits to display (default {DEFAULT_LIMIT}, "
                        f"max {MAX_LIMIT})")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC,
                   help=f"Network timeout in seconds (default {DEFAULT_TIMEOUT_SEC})")
    args = p.parse_args(argv)
    rc, text = query(args.pattern, timeout=args.timeout, limit=args.limit)
    print(text)
    return rc


if __name__ == "__main__":
    sys.exit(main())
