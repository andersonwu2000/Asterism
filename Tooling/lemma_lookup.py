"""Mathlib lemma signature lookup — `#check @<name>` via lake env lean.

When the agent's stderr surfaces an unknown / mistyped Mathlib name, or
the Manifest hands the agent a curated lemma list, the agent has only
the **name** — no signature, no parameter order, no instance shape.
Strong models recall this from training; weaker models hallucinate
arg counts and instance class. F20 closes the gap by fetching ground
truth at runtime: a real Lean session resolves each name and emits
its type.

Cost: `lake env lean` cold-starts in ~20s on this repo (Mathlib import
dominates). Batching every name a goal needs into ONE Lean session
amortizes that to a per-goal hit. A persistent JSON cache keyed on
toolchain version makes repeat queries free across goals AND across
daemon restarts.

Failures are silent: a name not found in Lean is recorded as
`found=False` in the cache and produces no Context.md bullet — we
never inject fabricated info, the raw stderr already carries the
error.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


CACHE_FILE = Path(__file__).parent / ".lemma_cache.json"
LOOKUP_TIMEOUT_SEC = 180  # generous; cold lake env lean ≈ 20-30s on this repo


@dataclass(frozen=True)
class LemmaInfo:
    name: str
    signature: str           # "" when found=False
    found: bool


def _toolchain_hash(workspace: Path) -> str:
    """Cache key fragment: SHA over the files that pin Lean + Mathlib
    versions. When `lake update` bumps a dep, the hash changes and the
    cache is implicitly invalidated."""
    parts: list[str] = []
    for fname in ("lean-toolchain", "lake-manifest.json"):
        p = workspace / fname
        if p.exists():
            parts.append(p.read_text(encoding="utf-8", errors="replace"))
    blob = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _load_cache(toolchain_hash: str) -> dict[str, LemmaInfo]:
    if not CACHE_FILE.exists():
        return {}
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if raw.get("toolchain_hash") != toolchain_hash:
        return {}
    return {
        n: LemmaInfo(**v) for n, v in raw.get("entries", {}).items()
    }


def _save_cache(toolchain_hash: str, entries: dict[str, LemmaInfo]) -> None:
    payload = {
        "toolchain_hash": toolchain_hash,
        "entries": {n: asdict(e) for n, e in entries.items()},
    }
    CACHE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# A `#check @<name>` block opens with the bare name at column 0 followed
# by ` : `. Continuation lines for long signatures are indented or wrap
# without a `<name> : ` marker.
_CHECK_BLOCK_RE = re.compile(
    r"^(?P<name>[\w.']+)\s*:\s*(?P<sig>.*?)(?=^[\w.']+\s*:|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _parse_check_output(output: str, names: list[str]) -> dict[str, str]:
    """Extract `name → signature` for each requested name found in
    `lake env lean` stdout. Names that produced an error (Lean printed
    `error(lean.unknownIdentifier): ...`) won't appear in the result.
    """
    found: dict[str, str] = {}
    name_set = set(names)
    for m in _CHECK_BLOCK_RE.finditer(output):
        nm = m.group("name")
        if nm in name_set and nm not in found:
            sig = m.group("sig").strip()
            # Strip trailing newlines that bleed in via DOTALL.
            sig = re.sub(r"\s+", " ", sig).strip()
            found[nm] = sig
    return found


def _build_query(names: list[str]) -> str:
    """One Mathlib import + one `#check @name` per requested name.

    `@` makes Lean print the fully-explicit signature including instance
    args, which is what weak models lack."""
    lines = ["import Mathlib", ""]
    lines.extend(f"#check @{n}" for n in names)
    return "\n".join(lines) + "\n"


def lookup_batch(
    lemma_names: list[str], workspace: Path,
) -> dict[str, LemmaInfo]:
    """Resolve lemma names against the workspace's Mathlib build.

    Returns a dict for every input name (including not-found, with
    `found=False`). Hits the persistent cache first; only the
    non-cached names spawn a real Lean session.
    """
    if not lemma_names:
        return {}

    # De-dup while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for n in lemma_names:
        if n not in seen:
            seen.add(n)
            unique.append(n)

    toolchain_hash = _toolchain_hash(workspace)
    cache = _load_cache(toolchain_hash)
    missing = [n for n in unique if n not in cache]

    if missing:
        query_path = workspace / ".lemma_lookup_query.lean"
        try:
            query_path.write_text(_build_query(missing), encoding="utf-8")
            r = subprocess.run(
                ["lake", "env", "lean", str(query_path)],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=LOOKUP_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            # Don't pollute cache; let the next call retry.
            return {n: cache.get(n, LemmaInfo(n, "", False)) for n in unique}
        finally:
            try:
                query_path.unlink()
            except OSError:
                pass

        # `#check` writes to stdout; `error(...)` to stderr. We parse
        # stdout for hits; misses (no block emitted) → found=False.
        sigs = _parse_check_output(r.stdout, missing)
        for name in missing:
            if name in sigs:
                cache[name] = LemmaInfo(name=name, signature=sigs[name],
                                        found=True)
            else:
                cache[name] = LemmaInfo(name=name, signature="", found=False)
        _save_cache(toolchain_hash, cache)

    return {n: cache[n] for n in unique}


# ---------------------------------------------------------------------
# Name extraction from stderr / proposal text — feeds lookup_batch
# ---------------------------------------------------------------------

# Dotted Mathlib-style identifiers: `ZMod.val_natCast`, `Nat.Prime.two_le`.
# Avoids matching plain words and short single-segment lowercase tokens.
_DOTTED_NAME_RE = re.compile(r"\b([A-Z][\w']*(?:\.[\w']+)+)\b")

# Names appearing in error / warning lines have the highest signal —
# they're the lemmas Lean specifically rejected.
_ERROR_LINE_RE = re.compile(
    r"(?im)^.*?(?:error|warning|Type mismatch|Unknown (?:constant|identifier)).*$",
)


def extract_lemma_names(stderr: str, *, max_names: int = 12) -> list[str]:
    """Pick out dotted Mathlib-style names from error / warning lines.

    Keeps lookup batch sizes bounded; first-seen order wins so the
    most relevant (earliest-error) names are kept when capped.
    """
    if not stderr:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for line in _ERROR_LINE_RE.findall(stderr):
        for m in _DOTTED_NAME_RE.finditer(line):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                out.append(name)
                if len(out) >= max_names:
                    return out
    return out
