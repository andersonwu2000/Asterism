"""miniF2F → Asterism Problem dir adapter.

Converts yangky11/miniF2F-lean4-style problem files into Asterism
`Problems/minif2f_<name>/` dirs (Manifest.md + Defs.lean). The Asterism
CLI's `init` command writes Root.lean afterwards.

miniF2F-lean4 ships one theorem per file under `MiniF2F/Valid/` and
`MiniF2F/Test/`. Canonical file form:

    import MiniF2F.Minif2fImport
    open BigOperators Real Nat Topology

    theorem <name> <binders>* : <conclusion> := by sorry

A few files have multiple theorems; this adapter emits one Problem dir
per theorem regardless.

Naming: original `<name>` (already a valid Lean identifier) prefixed with
`minif2f_` to coexist with hand-authored problems in the same workspace.

Lemma hints / strategic notes: left empty by default. miniF2F is a
black-box benchmark — we don't want to bias agents with per-problem
hints. Operators who want to compare with-hints vs without-hints can
edit the generated Manifest after import.
"""
from __future__ import annotations

import argparse
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
        return f"minif2f_{self.name}"


def parse_problem_file(path: Path) -> list[ProblemSpec]:
    """Extract every `theorem` declaration in a miniF2F .lean file.
    Returns [] if no theorem matched (helper file, comment-only, etc)."""
    text = path.read_text(encoding='utf-8')
    opens = [m.group(1).strip() for m in _OPEN_RE.finditer(text)]
    set_options = [m.group(1).strip() for m in _SET_OPTION_RE.finditer(text)]
    specs: list[ProblemSpec] = []
    for m in _THEOREM_RE.finditer(text):
        name = m.group(1).strip()
        sig = re.sub(r'\s+', ' ', m.group(2).strip()).strip()
        if not sig.startswith(':') and not sig:
            # Malformed — skip rather than crash
            continue
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


def _manifest_md(spec: ProblemSpec) -> str:
    """Generate Manifest.md content.

    Defaults:
      - Entry kind: Builder. miniF2F problems are high-school level
        single-shot leaves; Backward decomposition rarely helps. If
        Builder runs out of attempts, framework can re-dispatch as
        Backward via cascade.
      - axioms_whitelist: standard Mathlib trio. Matches what
        `library.promote` would have accepted historically.
      - lemma_hints / strategic_notes: empty. Benchmark integrity —
        per-problem hints would bias the agent toward expected
        strategies. Operators who want a with-hints variant should
        run a separate experiment with manually-edited manifests.
    """
    return (
        f"---\n"
        f"problem: {spec.slug}\n"
        f"axioms_whitelist:\n"
        f"  - propext\n"
        f"  - Quot.sound\n"
        f"  - Classical.choice\n"
        f"forbidden_lemmas: []\n"
        f"---\n"
        f"\n"
        f"# {spec.slug} — imported from miniF2F\n"
        f"\n"
        f"Original miniF2F theorem name: `{spec.name}`.\n"
        f"\n"
        f"## Statement\n"
        f"{spec.signature}\n"
        f"\n"
        f"## Entry kind\n"
        f"Builder\n"
        f"\n"
        f"## Lemma hints\n"
        f"\n"
        f"## Strategic notes\n"
        f"Imported via `python -m Tooling.adapters.minif2f`. No\n"
        f"per-problem hints — benchmark integrity (compare against\n"
        f"LeanDojo / DeepSeek-Prover head-to-head on the same\n"
        f"problem distribution).\n"
    )


def emit_problem_dir(spec: ProblemSpec, output_root: Path) -> Path:
    """Materialize Problems/<slug>/{Manifest.md, Defs.lean}.

    Idempotent: re-running on an existing slug overwrites Manifest.md
    + Defs.lean. Does NOT touch proofs/ or Root.lean — those are owned
    by `asterism init` and the dispatcher cascade. Operators who want
    a clean re-import should `asterism reset <slug>` first.
    """
    pdir = output_root / spec.slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text(_defs_lean(spec), encoding="utf-8")
    (pdir / "Manifest.md").write_text(_manifest_md(spec), encoding="utf-8")
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
    `minif2f_` slug prefix). Useful to slice a single section, e.g.
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
    print(f"\nNext step: init each problem, then run the daemon:")
    print(f"  for d in Problems/minif2f_*; do")
    print(f"      python -m Tooling.cli init \"$(basename $d)\"")
    print(f"  done")
    print(f"  python -m Tooling.cli run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
