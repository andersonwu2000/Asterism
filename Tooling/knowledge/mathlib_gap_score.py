"""Mathlib gap depth scoring for stress-target selection.

Forecasts how much stress a candidate Problem will put on the
framework, by measuring how many of the identifiers the Manifest
references are already in Mathlib (low coverage → high gap →
framework will have to build prerequisites from scratch → high
stress signal; high coverage → framework walks a fast lane →
weak stress signal).

Empirical motivation (2026-05-22, post-pi1_circle stress retro):
residue_thm with low Mathlib coverage surfaced 8 framework bugs in
~500 goals; pi1_circle with high Mathlib coverage surfaced 0 in 24
goals. Picking the next stress target on gut alone is unreliable —
this gives a 0-10 number to anchor the decision.

Method (v0, simple):
- Extract Lean identifiers from the Manifest:
  * back-tick quoted dotted identifiers in body (`Foo.bar.baz`)
  * Lemma hints section entries (one identifier per `- ` bullet)
- For each identifier, count occurrences of its short name
  (`baz` of `Foo.bar.baz`) in Mathlib `.lean` source using `rg`
  (or a Python fallback if rg is missing).
- coverage = identifiers_with_hit / total_identifiers
- gap_score = 10 * (1 - coverage)
- stress prediction: <4 low, 4-7 med, >=7 high.

Limitations to know:
- Short-name match is over-permissive (any `def baz` anywhere counts)
  — but for ranking candidates it's directionally right.
- Identifiers that don't appear in the Manifest (because user wrote
  prose instead of citing API names) lower input quality. Workaround:
  encourage Manifest authors to back-tick key API names.
- Mathlib coverage ≠ proof-tractability — a high-coverage problem
  can still surface framework bugs in other dimensions (OR-parallel,
  escalation thresholds). Treat the score as ONE input, not the only one.

Usage:
    python -m Tooling.knowledge.mathlib_gap_score Problems/pi1_circle/Manifest.md
    python -m Tooling.knowledge.mathlib_gap_score Problems/pi1_circle/
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from ..state import manifest


MATHLIB_REL = ".lake/packages/mathlib/Mathlib"

# Back-tick quoted dotted identifier in markdown body, e.g. `Foo.bar.baz`.
# Single-segment back-tick (`foo`) is too noisy — could be prose, file
# extension, or short variable name. Require at least one dot.
_BACKTICK_ID_RE = re.compile(
    r"`([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)`"
)

# Capitalized Lean identifier (possibly dotted), as it appears in raw
# Statement / Defs.lean source. Convention: types/structures/classes
# capitalize their first segment; qualified names like
# `Complex.windingNumber` start with a capital. Functions/lemmas in
# the Statement are usually dotted (qualified) — `Set.MapsTo`,
# `Complex.windingNumber`. Pure camelCase first-letter-lowercase tokens
# (`deriv`, `dist`) are too noisy to extract without context, so we
# skip them and rely on back-tick / hints for those.
_STATEMENT_ID_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\b"
)

# Prose words that match _STATEMENT_ID_RE shape but aren't Lean
# identifiers — filter to reduce noise when Statement / notes mix
# English prose with Lean syntax.
_PROSE_SKIP = {"i.e", "e.g", "U.S", "etc"}


def extract_identifiers(mfst) -> list[str]:
    """Pull dotted Lean identifiers from a parsed Manifest.

    Sources:
    - back-tick quoted dotted ids in Statement / Strategic notes / Lemma hints
    - capitalized dotted ids in raw Statement (Lean source, no back-tick)
    - first token of each `- ` bullet in lemma_hints / mathlib_hints
    Deduped, sorted for stable output.
    """
    text_blob = (
        (mfst.statement or "")
        + "\n"
        + (mfst.strategic_notes or "")
        + "\n"
        + "\n".join(f"- `{h}`" for h in (mfst.all_hints or []))
    )
    ids: set[str] = set()
    ids.update(_BACKTICK_ID_RE.findall(text_blob))
    # Statement is raw Lean: extract capitalized dotted tokens directly.
    for ident in _STATEMENT_ID_RE.findall(mfst.statement or ""):
        if ident in _PROSE_SKIP:
            continue
        ids.add(ident)
    # Hints section entries as raw bullets (in case the user didn't
    # wrap them in back-ticks):
    for h in mfst.all_hints or []:
        # Hints sometimes contain a hint description after the
        # identifier, e.g. "- `Foo.bar` — does X". Strip after the
        # first whitespace / non-identifier char.
        m = re.match(r"`?([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)`?", h)
        if m:
            ids.add(m.group(1))
    return sorted(ids)


def _rg_count(short: str, mathlib_dir: Path) -> int | None:
    """Return aggregate `\\bshort\\b` count in mathlib via `rg`, or None
    if rg is unavailable so the caller can fall back."""
    pattern = rf"\b{re.escape(short)}\b"
    try:
        out = subprocess.check_output(
            ["rg", "-c", "-t", "lean", pattern, str(mathlib_dir)],
            stderr=subprocess.DEVNULL, text=True,
        )
    except FileNotFoundError:
        return None
    except subprocess.CalledProcessError as e:
        # rg exits 1 when zero matches — that's a valid answer.
        if e.returncode == 1:
            return 0
        return None
    total = 0
    for line in out.splitlines():
        if ":" in line:
            try:
                total += int(line.rsplit(":", 1)[1])
            except ValueError:
                continue
    return total


def _python_count(short: str, mathlib_dir: Path) -> int:
    """Fallback grep when rg is missing — slower but portable."""
    pattern = re.compile(rf"\b{re.escape(short)}\b")
    total = 0
    for root, _dirs, files in os.walk(mathlib_dir):
        for f in files:
            if not f.endswith(".lean"):
                continue
            try:
                with open(os.path.join(root, f), "r", encoding="utf-8",
                          errors="replace") as fh:
                    for line in fh:
                        total += len(pattern.findall(line))
            except OSError:
                continue
    return total


# Short-name grep can't disambiguate when the last dotted segment is
# a Lean keyword — `Fejer.theorem` would match `theorem` everywhere in
# mathlib. Treat these as miss + flag in the per-id rendering so the
# operator notices and renames (`Fejer.cesaro_mean_uniform`, etc.).
_LEAN_KEYWORD_TAILS = {
    "theorem", "lemma", "def", "structure", "class", "instance",
    "abbrev", "axiom", "constant", "variable", "namespace", "section",
    "open", "import", "by", "fun", "let", "match", "with", "if",
    "then", "else", "do", "return", "in", "where", "have", "show",
    "from", "exact",
}


def mathlib_count(identifier: str, mathlib_dir: Path) -> int:
    short = identifier.split(".")[-1]
    if short in _LEAN_KEYWORD_TAILS:
        return -1  # signal to renderer; counts as 0 hit for score.
    c = _rg_count(short, mathlib_dir)
    if c is None:
        c = _python_count(short, mathlib_dir)
    return c


def load_toolkit_file(path: Path) -> list[str]:
    """Read an operator-curated expected-toolkit list. Format: one
    identifier per line. `#` line comments allowed. Optional
    description after the first whitespace token (ignored — kept so
    the list doubles as human-readable rationale)."""
    ids: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        tok = s.split()[0].strip("`")
        if tok and tok not in seen:
            seen.add(tok)
            ids.append(tok)
    return ids


def score(ids: list[str], label: str, workspace: Path) -> dict:
    """Compute gap score for the given identifier list.

    `label` is just for display (problem name, or toolkit file name
    when there's no Manifest). Caller decides whether ids come from
    Manifest auto-extraction or operator-curated toolkit file.
    """
    mathlib = workspace / MATHLIB_REL
    if not mathlib.exists():
        raise FileNotFoundError(f"mathlib not found at {mathlib}")
    per_id: dict[str, int] = {}
    hits = 0
    for ident in ids:
        c = mathlib_count(ident, mathlib)
        per_id[ident] = c
        if c > 0:  # -1 (keyword tail) and 0 (miss) both don't count
            hits += 1
    total = len(ids)
    coverage = (hits / total) if total else 0.0
    gap = 10.0 * (1.0 - coverage)
    if gap >= 7:
        pred = "high"
    elif gap >= 4:
        pred = "med"
    else:
        pred = "low"
    return {
        "problem": label,
        "total": total,
        "hits": hits,
        "coverage": coverage,
        "gap_score": gap,
        "stress_prediction": pred,
        "per_identifier": per_id,
    }


def render(r: dict) -> str:
    lines = []
    lines.append(f"# Mathlib gap score: {r['problem']}")
    lines.append(
        f"identifiers={r['total']}  hits={r['hits']}  "
        f"coverage={r['coverage']:.0%}"
    )
    lines.append(
        f"GAP SCORE = {r['gap_score']:.1f}/10  "
        f"-> stress prediction: {r['stress_prediction'].upper()}"
    )
    lines.append("")
    lines.append("per-identifier (short-name mathlib hit count, low first):")
    for ident, c in sorted(r["per_identifier"].items(), key=lambda kv: (kv[1], kv[0])):
        if c == -1:
            marker = "SKIP"
            detail = "tail is a Lean keyword; rename and rerun"
        elif c == 0:
            marker = "MISS"; detail = "n=0"
        elif c < 5:
            marker = "low "; detail = f"n={c}"
        else:
            marker = "hit "; detail = f"n={c}"
        lines.append(f"  [{marker}] {ident:50}  {detail}")
    if r["total"] == 0:
        lines.append("")
        lines.append(
            "WARNING: Manifest references 0 dotted identifiers — score "
            "input quality is poor. Add back-tick quoted API names to "
            "Strategic notes / Lemma hints for a meaningful score."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "target", nargs="?",
        help="Path to Manifest.md OR to a Problems/<slug>/ directory. "
             "Optional when --expected-toolkit is provided.",
    )
    ap.add_argument(
        "--expected-toolkit", type=Path, default=None,
        help="Path to a plain-text file listing the mathlib identifiers "
             "this Problem is expected to use. One identifier per line; "
             "`#` comments and optional descriptions after the first "
             "whitespace token are allowed. Overrides Manifest "
             "auto-extraction — use this for forward-looking candidate "
             "scoring when the Manifest doesn't yet list expected API.",
    )
    ap.add_argument(
        "--workspace", type=Path, default=Path.cwd(),
        help="Repo root (default: cwd). mathlib is read from "
             f"<workspace>/{MATHLIB_REL}/.",
    )
    args = ap.parse_args(argv)

    if args.target is None and args.expected_toolkit is None:
        ap.error("must provide either target Manifest path or --expected-toolkit")

    # Resolve ids + display label.
    label = None
    if args.expected_toolkit is not None:
        if not args.expected_toolkit.exists():
            print(f"FAIL: toolkit file {args.expected_toolkit} not found",
                  file=sys.stderr)
            return 1
        ids = load_toolkit_file(args.expected_toolkit)
        label = args.expected_toolkit.stem

    if args.target is not None:
        p = Path(args.target)
        if p.is_dir():
            p = p / "Manifest.md"
        if not p.exists():
            print(f"FAIL: {p} not found", file=sys.stderr)
            return 1
        mfst = manifest.parse(p)
        # Manifest path always wins as label when present.
        label = (mfst.problem + " (toolkit override)") if args.expected_toolkit \
            else mfst.problem
        if args.expected_toolkit is None:
            ids = extract_identifiers(mfst)

    r = score(ids, label, args.workspace)
    print(render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
