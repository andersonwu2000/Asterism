"""Pin-truth oracle for externally-sourced declaration names.

Loogle indexes LIVE Mathlib; this project builds against a pinned
older revision. Every "loogle verified it exists" claim is therefore
unsound against the pin (task #149: two substitute deliverables
shipped on phantom lemmas). This module kills the class at the tool
boundary: every name a search tool returns gets annotated with pin
truth before any agent reads it.

Truth source: the gateway's live Lean environment (`/verify` borrow
entry with a `#check @<fq-name>` probe file) — the elaborator, not a
source grep, because `to_additive`/`alias`-generated names never
appear literally in Mathlib sources.

Cost model (operator ruling 2026-08-03): a borrow probe evicts one
warm gateway slot, so the gateway is only consulted on cache misses.
`(pin_rev, decl) → present` is immutable while the pin stands, so a
persistent sqlite cache (`.asterism/pin_decl_cache.db`) makes the
steady state free and a ten-hit query one probe, not ten.

Probe names are sent EXACTLY as the search tool returned them (fully
qualified). A failed probe means "this name does not elaborate as
written" — which is precisely the citation question — and nothing
more; the label wording must not claim the mathematics is absent.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

PROBE_TIMEOUT_SEC = 240   # cold `import Mathlib` warmup on a borrowed
                          # slot can take minutes; cache makes it rare
CACHE_BUSY_MS = 5000      # concurrent spawns share one cache file

#: tri-state: True = elaborates against the pin, False = does not,
#: None = could not be determined this call (gateway down, import
#: failure) — never cached, never presented as a verdict.
PinVerdict = "bool | None"


def workspace_root(start: "Path | None" = None) -> "Path | None":
    """Nearest ancestor holding lake-manifest.json (spawn cwd is
    always inside the workspace)."""
    p = (start or Path.cwd()).resolve()
    for d in (p, *p.parents):
        if (d / "lake-manifest.json").exists():
            return d
    return None


def pin_rev(root: "Path | None" = None) -> "str | None":
    root = root or workspace_root()
    if root is None:
        return None
    try:
        m = json.loads((root / "lake-manifest.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for pkg in m.get("packages", []):
        if pkg.get("name") == "mathlib":
            return pkg.get("rev") or None
    return None


def _cache(root: Path) -> sqlite3.Connection:
    path = root / ".asterism" / "pin_decl_cache.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=CACHE_BUSY_MS / 1000)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS decl_pin ("
        " pin_rev TEXT NOT NULL, decl TEXT NOT NULL,"
        " present INTEGER NOT NULL, checked_at TEXT NOT NULL,"
        " PRIMARY KEY (pin_rev, decl))")
    return conn


def _gateway_probe(root: Path, names: "list[str]") -> "dict[str, bool] | None":
    """One `/verify` borrow for the whole batch. Returns None when the
    probe as a whole is inconclusive (gateway down, import error)."""
    port = os.environ.get("ASTERISM_GATEWAY_PORT", "8765")
    tmp_dir = root / ".asterism" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    probe = tmp_dir / f"pin_probe_{os.getpid()}.lean"
    # Line i+2 (1-based) carries names[i]; diagnostics map back by line.
    probe.write_text(
        "import Mathlib\n"
        + "".join(f"#check @{n}\n" for n in names),
        encoding="utf-8")
    body = json.dumps({"target_path": str(probe),
                       "write_olean": False}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/verify", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT_SEC) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError,
            ValueError, OSError):
        return None
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    if "diagnostics" not in data:
        return None
    bad_lines: set[int] = set()
    for d in data["diagnostics"]:
        if d.get("severity") != "error":
            continue
        for ln in (d.get("line", 0), *(d.get("also_lines") or [])):
            bad_lines.add(int(ln))
    if 1 in bad_lines:
        return None          # the import itself failed — no verdicts
    return {n: (i + 2) not in bad_lines for i, n in enumerate(names)}


def check_names(names: "list[str]") -> "dict[str, bool | None]":
    """Pin verdict per name, cache-first. Unknown-on-failure, never
    a false green: any inconclusive path yields None."""
    out: "dict[str, bool | None]" = {n: None for n in names}
    if not names:
        return out
    root = workspace_root()
    rev = pin_rev(root)
    if root is None or rev is None:
        return out
    try:
        conn = _cache(root)
    except sqlite3.Error:
        return out
    try:
        qmarks = ",".join("?" * len(names))
        for decl, present in conn.execute(
                f"SELECT decl, present FROM decl_pin"
                f" WHERE pin_rev = ? AND decl IN ({qmarks})",
                (rev, *names)):
            out[decl] = bool(present)
        misses = [n for n in names if out[n] is None]
        if misses:
            probed = _gateway_probe(root, misses)
            if probed is not None:
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                conn.executemany(
                    "INSERT OR REPLACE INTO decl_pin"
                    " (pin_rev, decl, present, checked_at)"
                    " VALUES (?,?,?,?)",
                    [(rev, n, int(v), now) for n, v in probed.items()])
                conn.commit()
                out.update(probed)
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return out


def label(verdict: "bool | None") -> str:
    """The per-hit annotation agents read. False wording deliberately
    says "under this name" — the probe answers citability, not
    existence of the mathematics."""
    if verdict is True:
        return "[in pin]"
    if verdict is False:
        return "[NOT in pin under this name — do not cite as-is]"
    return "[pin: unverified]"
