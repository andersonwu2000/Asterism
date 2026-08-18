"""miniF2F → Asterism Problem dir adapter.

Converts yangky11/miniF2F-lean4-style problem files into Asterism
`Problems/Minif2f/<name>/` dirs (problem.json + Defs.lean). The Asterism
CLI's `init` command writes Root.lean afterwards.

miniF2F-lean4 ships one theorem per file under `MiniF2F/Valid/` and
`MiniF2F/Test/`. Canonical file form:

    import MiniF2F.Minif2fImport
    open BigOperators Real Nat Topology

    theorem <name> <binders>* : <conclusion> := by sorry

A few files have multiple theorems; this adapter emits one Problem dir
per theorem regardless.

Naming: each theorem gets a dot-separated slug `Minif2f.<name>` matching
the nested Problems layout. The framework's `db.problem_dir` helper
resolves `Minif2f.<name>` to `Problems/Minif2f/<name>/` on disk, while
Lean module/namespace paths use `Problems.Minif2f.<name>.<...>`
naturally (dots are Lean's native namespace separator).

Lemma hints / strategic notes: left empty by default. miniF2F is a
black-box benchmark — we don't want to bias agents with per-problem
hints. Operators who want to compare with-hints vs without-hints can
edit the generated seed after import.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# `theorem NAME ... :=` — lazy match through first `:=`. Captures the
# theorem name (\S+) and everything between it and `:=` (binders +
# conclusion). Note: this would mis-fire on a binder default like
# `(n : Nat := 0)` — miniF2F problems don't use those, but flag it
# in failure reports if it happens.
_THEOREM_RE = re.compile(
    r'^theorem\s+(\S+)([\s\S]*?)\s*:=',
    re.MULTILINE,
)
_OPEN_RE = re.compile(r'^open\s+(.+?)\s*$', re.MULTILINE)
# miniF2F problems set `maxHeartbeats 0` to allow unbounded elaboration
# time per declaration. Preserve so Asterism-generated proofs inherit the
# same allowance.
_SET_OPTION_RE = re.compile(r'^set_option\s+(.+?)\s*$', re.MULTILINE)
# Files we know aren't problem files in miniF2F-lean4 layout
_NON_PROBLEM_FILES = frozenset([
    "Minif2fImport.lean",
])


@dataclass
class ProblemSpec:
    name: str          # original theorem name (Lean identifier)
    signature: str     # text between `theorem NAME` and `:=`, trimmed
    opens: list[str]   # `open Foo Bar` clauses replayed in Defs.lean
    set_options: list[str] = field(default_factory=list)  # set_option clauses
    source_file: Path | None = None  # for traceability

    @property
    def slug(self) -> str:
        # Nested Problems layout (db.problem_dir maps `.` → `/`):
        # slug 'Minif2f.algebra_1' resolves to Problems/Minif2f/algebra_1/.
        return f"Minif2f.{self.name}"

    @property
    def rel_dir(self) -> Path:
        # `Minif2f/<name>` as a relative path under Problems/.
        return Path("Minif2f", self.name)


def _normalize_signature(sig: str) -> str:
    """Convert Lean theorem signature `(binders) : conclusion` form to a
    self-contained type expression `∀ (binders), conclusion`.

    miniF2F files have `theorem <name> (a b : ℝ) (h : ...) : <type> := by sorry`.
    The raw signature captured between `theorem <name>` and `:=` is
    `(a b : ℝ) (h : ...) : <type>`. Asterism's `cmd_init` then wraps the
    charter's statement as `theorem main : {statement} := by sorry` —
    producing `theorem main : (a b : ℝ) (h : ...) : <type> := by sorry`,
    which has DOUBLE COLON (invalid Lean syntax). Backward agents reading
    that broken Root.lean copy the same broken pattern into their patch
    files; lake_build_error → exhausted → 0 proofs.

    Fix: pre-normalize the signature so `cmd_init`'s wrapper produces
    valid Lean. Use `∀` to bind the parameters, comma to separate from
    the conclusion. The result composes correctly under `theorem main : `.

    Depth-aware: tracks paren/bracket/brace nesting so colons INSIDE
    binder groups (e.g. `(x : ℝ)`) aren't mistaken for the binder/
    conclusion separator.

    Edge cases:
      - Nullary signature `: P`  →  `P`
      - Just `P` (no leading colon, no binders) → `P`
      - `(a : ℝ) : x = x` → `∀ (a : ℝ), x = x`
      - `{X : Type} [Inst X] (x : X) : True` → `∀ {X : Type} [Inst X] (x : X), True`
    """
    sig = sig.strip()
    if not sig:
        return sig
    depth = 0
    sep_idx = -1
    for i, ch in enumerate(sig):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            sep_idx = i
            break
    if sep_idx == -1:
        # No top-level `:` — signature is already a bare type expression.
        return sig
    binders = sig[:sep_idx].strip()
    conclusion = sig[sep_idx + 1:].strip()
    if not binders:
        return conclusion
    return f"∀ {binders}, {conclusion}"


def parse_problem_file(path: Path) -> list[ProblemSpec]:
    """Extract every `theorem` declaration in a miniF2F .lean file.
    Returns [] if no theorem matched (helper file, comment-only, etc)."""
    text = path.read_text(encoding='utf-8')
    opens = [m.group(1).strip() for m in _OPEN_RE.finditer(text)]
    set_options = [m.group(1).strip() for m in _SET_OPTION_RE.finditer(text)]
    specs: list[ProblemSpec] = []
    for m in _THEOREM_RE.finditer(text):
        name = m.group(1).strip()
        raw_sig = re.sub(r'\s+', ' ', m.group(2).strip()).strip()
        if not raw_sig:
            continue
        sig = _normalize_signature(raw_sig)
        specs.append(ProblemSpec(
            name=name, signature=sig, opens=opens,
            set_options=set_options, source_file=path,
        ))
    return specs


def _defs_lean(spec: ProblemSpec) -> str:
    """Generate Defs.lean content. Pure-Mathlib problems get `import
    Mathlib` + replayed set_options + replayed opens. Empty namespace
    block satisfies the Asterism convention of having a
    `Problems.<slug>` namespace available for sub-goal aliases the
    framework may inject later."""
    body = "import Mathlib\n\n"
    for clause in spec.set_options:
        body += f"set_option {clause}\n"
    if spec.set_options:
        body += "\n"
    for clause in spec.opens:
        body += f"open {clause}\n"
    if spec.opens:
        body += "\n"
    body += (
        f"namespace Problems.{spec.slug}\n"
        f"\n"
        f"end Problems.{spec.slug}\n"
    )
    return body


def _problem_seed(spec: ProblemSpec) -> str:
    """Generate problem.json seed content (v40 — Manifest.md retired).

    Defaults:
      - axioms_whitelist: standard Mathlib trio. Matches what
        `library.promote` would have accepted historically.
      - No hints in the charter beyond the statement. Benchmark
        integrity — per-problem hints would bias the agent toward
        expected strategies. Operators who want a with-hints variant
        should run a separate experiment with edited seeds.
    """
    charter = (
        f"# {spec.slug} — imported from miniF2F\n"
        f"\n"
        f"Original miniF2F theorem name: `{spec.name}`.\n"
        f"\n"
        f"{spec.signature}\n"
        f"\n"
        f"Imported via `Benchmarks/minif2f/adapter.py`. No per-problem\n"
        f"hints — benchmark integrity (compare against LeanDojo /\n"
        f"DeepSeek-Prover head-to-head on the same problem\n"
        f"distribution).\n"
    )
    return json.dumps({
        "problem": spec.slug,
        "charter": charter,
        "settings": {
            "axioms_whitelist": ["propext", "Quot.sound",
                                 "Classical.choice"],
            "forbidden_lemmas": [],
            "library": False,
            "signoff": False,
        },
    }, indent=2, ensure_ascii=False) + "\n"


def emit_problem_dir(spec: ProblemSpec, output_root: Path) -> Path:
    """Materialize Problems/Minif2f/<name>/{problem.json, Defs.lean}.

    `output_root` should point at the workspace's `Problems/` directory;
    the adapter creates the `Minif2f/` subdir for benchmark isolation.

    Idempotent: re-running on an existing slug overwrites problem.json
    + Defs.lean. Does NOT touch proofs/ or Root.lean — those are owned
    by `asterism init` and the dispatcher cascade. Operators who want
    a clean re-import should `asterism reset <slug>` first.
    """
    pdir = output_root / spec.rel_dir
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text(_defs_lean(spec), encoding="utf-8")
    (pdir / "problem.json").write_text(_problem_seed(spec),
                                       encoding="utf-8")
    return pdir


@dataclass
class ImportResult:
    imported: list[str] = field(default_factory=list)
    skipped_no_theorem: list[str] = field(default_factory=list)
    skipped_filter: list[str] = field(default_factory=list)


def import_minif2f(
    source: Path, output: Path, *,
    prefix_filter: str | None = None,
    limit: int | None = None,
) -> ImportResult:
    """Walk `source` directory, parse each .lean, emit Problem dirs.

    `prefix_filter` matches the ORIGINAL theorem name (before the
    `Minif2f.` slug prefix). Useful to slice a single section, e.g.
    `algebra_` or `mathd_numbertheory_`.
    """
    result = ImportResult()
    for p in sorted(source.glob("*.lean")):
        if p.name in _NON_PROBLEM_FILES:
            continue
        specs = parse_problem_file(p)
        if not specs:
            result.skipped_no_theorem.append(p.name)
            continue
        for spec in specs:
            if prefix_filter and not spec.name.startswith(prefix_filter):
                result.skipped_filter.append(spec.name)
                continue
            emit_problem_dir(spec, output)
            result.imported.append(spec.slug)
            if limit is not None and len(result.imported) >= limit:
                return result
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert miniF2F Lean 4 problems to Asterism Problem dirs.",
    )
    parser.add_argument(
        "--source", type=Path, required=True,
        help="miniF2F directory holding *.lean files "
             "(e.g. ../miniF2F-lean4/MiniF2F/Valid)",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Asterism Problems/ root (e.g. ./Problems)",
    )
    parser.add_argument(
        "--filter", type=str, default=None,
        help="Only import theorems whose ORIGINAL name starts with this "
             "prefix (e.g. 'algebra_' / 'mathd_').",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of problems to import (after filter).",
    )
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print(f"FAIL: source {args.source} is not a directory",
              file=sys.stderr)
        return 1
    args.output.mkdir(parents=True, exist_ok=True)

    result = import_minif2f(
        args.source, args.output,
        prefix_filter=args.filter, limit=args.limit,
    )
    print(f"Imported {len(result.imported)} problem(s).")
    for slug in result.imported[:10]:
        print(f"  {slug}")
    if len(result.imported) > 10:
        print(f"  ... ({len(result.imported) - 10} more)")
    if result.skipped_no_theorem:
        print(f"\nSkipped {len(result.skipped_no_theorem)} file(s) "
              f"(no theorem found).")
    if result.skipped_filter:
        print(f"Skipped {len(result.skipped_filter)} theorem(s) "
              f"by --filter.")
    print(f"\nNext step: bulk-init the batch, then run scoped:")
    print(f"  python -m Tooling.core.cli init-batch Problems/Minif2f")
    print(f"  python -m Tooling.core.cli run --scope 'Minif2f.%'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
