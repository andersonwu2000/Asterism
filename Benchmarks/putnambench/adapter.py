"""PutnamBench → Asterism Problem dir adapter.

Converts trishullab/PutnamBench Lean 4 problem files into Asterism
`Problems/Putnam/<name>/` dirs. Unlike the early miniF2F adapter era,
`asterism init` no longer generates Root.lean from the charter — Root
and Defs are user-pinned inputs — so this adapter emits all three
files itself:

  Defs.lean     author-vouched vocabulary layer: the `_solution`
                abbrev with the OFFICIAL answer filled in (upstream
                keeps it as `:= sorry` + a `-- <answer>` comment;
                this is the `solutions_replaced` evaluation protocol,
                expressed as a separate reducible definition instead
                of textual inlining) plus any auxiliary `def`s the
                statement uses, in original file order.
  Root.lean     canonical `theorem main : <∀-form> := by sorry`,
                statement byte-derived from the upstream theorem
                signature (binders → `∀` closure; NEVER hand-edited).
  problem.json  informal problem text (the upstream docstring) as the
                human-readable Statement + provenance; `library: false`
                (benchmark problems are not Library material).

Canonical upstream file shape (one theorem per file, proof = sorry):

    import Mathlib

    open Filter Topology

    [noncomputable] abbrev putnam_YYYY_sN_solution : T := sorry
    -- <official answer, single line>
    [def aux ...]*
    /--
    <informal statement, LaTeX>
    -/
    theorem putnam_YYYY_sN <binders>* : <conclusion> :=
    sorry

Benchmark integrity: statements are never edited. Problems whose
statements do not elaborate on this workspace's toolchain (upstream
pins an older Lean/Mathlib) are EXCLUDED and logged by the prep
driver, not fixed. No per-problem hints in Strategic notes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


_IMPORT_RE = re.compile(r'^import\s+(\S+)\s*$')
_OPEN_RE = re.compile(r'^open\s+(.+?)\s*$')
_SET_OPTION_RE = re.compile(r'^set_option\s+(.+?)\s*$')
_DECL_START_RE = re.compile(
    r'^(?:noncomputable\s+)?(?:abbrev|def|inductive|structure)\s')
# Solution abbrevs are single-line by upstream construction (their own
# scripts/rewrite_solutions.py depends on it, CI-checked).
_ABBREV_RE = re.compile(
    r'^(?:noncomputable\s+)?abbrev\s+(\S+)\s*:\s*(.+?)\s*:=\s*sorry\s*$')
# The theorem block runs to end-of-file; the proof is always `sorry`.
# Greedy signature match anchored on the FINAL `:= sorry` so internal
# `:=` (e.g. `let x := e` inside the statement) can't truncate it.
_THEOREM_RE = re.compile(
    r'^theorem\s+(\S+)([\s\S]*):=\s*(?:by\s+)?sorry\s*$')


@dataclass
class ProblemSpec:
    name: str               # original theorem name, e.g. putnam_1962_a1
    signature: str          # ∀-normalized statement (upstream line
                            # structure preserved; comments stripped)
    opens: list[str]        # `open ...` clauses, file order
    set_options: list[str]  # `set_option ...` clauses
    decls: list[str]        # Defs.lean decl blocks (solution abbrev with
                            # official answer substituted + aux defs),
                            # original file order, verbatim otherwise
    informal: str = ""      # docstring text (informal statement)
    solution_name: str = "" # abbrev name if the problem has one
    source_file: Path | None = None

    @property
    def slug(self) -> str:
        # Nested Problems layout (db.problem_dir maps `.` → `/`).
        return f"Putnam.{self.name}"

    @property
    def rel_dir(self) -> Path:
        return Path("Putnam", self.name)


class AdapterError(ValueError):
    """Upstream file departs from the canonical shape. Fail loud —
    silently mangling a benchmark statement is worse than skipping."""


def _strip_line_comments(sig: str) -> str:
    """Drop `-- ...` comments from a signature. Two upstream files
    annotate binders with inline comments; keeping them would make
    every downstream textual statement comparison see comment noise,
    and collapsing whitespace across them corrupts the statement."""
    out = []
    for line in sig.splitlines():
        cut = line.find("--")
        if cut != -1:
            line = line[:cut].rstrip()
        if line.strip():
            out.append(line)
    return "\n".join(out)


def _normalize_signature(sig: str) -> str:
    """Convert `(binders)* : conclusion` to a self-contained type
    expression `∀ (binders)*,\\n<conclusion>` so it composes under
    `theorem main : {statement}`. LINE-PRESERVING: upstream newlines
    are kept because they are syntactically significant in Lean —
    a `let x := e` inside a statement is terminated by the line
    break, so one-line collapsing produces a parse error (learned
    from putnam_1965_b4; 17 corpus statements contain `let`).
    Multi-line `goals.statement` is the workspace norm (49 research
    roots). Depth-aware separator scan: colons inside binder groups /
    set-builders are not mistaken for the binder/conclusion split."""
    sig = _strip_line_comments(sig).strip()
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
        return sig
    binders = sig[:sep_idx].strip()
    conclusion = sig[sep_idx + 1:].strip()
    if not binders:
        return conclusion
    return f"∀ {binders},\n{conclusion}"


def parse_problem_file(path: Path) -> ProblemSpec:
    """Parse one PutnamBench src/*.lean file. Raises AdapterError on
    any departure from the canonical shape."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    opens: list[str] = []
    set_options: list[str] = []
    decls: list[str] = []
    solution_name = ""
    informal = ""
    theorem_start: int | None = None

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("--"):
            # Stray top-level note comment (52 files carry e.g.
            # "--Note: The original problem ..."). Skip; the SOLUTION
            # comment is consumed in the abbrev branch, never here.
            i += 1
        elif m := _IMPORT_RE.match(line):
            if m.group(1) != "Mathlib":
                raise AdapterError(f"{path.name}: unexpected import "
                                   f"`{m.group(1)}` (expected Mathlib)")
            i += 1
        elif m := _OPEN_RE.match(line):
            opens.append(m.group(1))
            i += 1
        elif m := _SET_OPTION_RE.match(line):
            set_options.append(m.group(1))
            i += 1
        elif line.startswith("/--"):
            # Docstring block up to closing `-/`.
            j = i
            while j < n and "-/" not in lines[j]:
                j += 1
            if j >= n:
                raise AdapterError(f"{path.name}: unterminated docstring")
            block = "\n".join(lines[i:j + 1])
            informal = block[block.index("/--") + 3:
                             block.rindex("-/")].strip()
            i = j + 1
        elif line.startswith("theorem "):
            theorem_start = i
            break
        elif _DECL_START_RE.match(line):
            if m := _ABBREV_RE.match(line):
                # Solution abbrev: substitute the official answer from
                # the comment line that immediately follows. Always
                # `noncomputable` — the filled value may not compile
                # (ℝ arithmetic etc.); upstream never compiles it
                # because `sorry` short-circuits.
                if solution_name:
                    raise AdapterError(
                        f"{path.name}: multiple solution abbrevs")
                if i + 1 >= n or not lines[i + 1].lstrip().startswith("--"):
                    raise AdapterError(
                        f"{path.name}: abbrev without `--` answer comment")
                solution_name = m.group(1)
                sol_type = m.group(2)
                answer = lines[i + 1].lstrip()[2:].strip()
                decls.append(f"noncomputable abbrev {solution_name} : "
                             f"{sol_type} := {answer}")
                i += 2
            else:
                # Aux def (possibly multi-line pattern-matching):
                # verbatim block until the next decl / docstring /
                # theorem / blank line at top level.
                j = i + 1
                while j < n:
                    nxt = lines[j]
                    if (not nxt.strip() or _DECL_START_RE.match(nxt)
                            or nxt.startswith("/--")
                            or nxt.startswith("theorem ")):
                        break
                    j += 1
                decls.append("\n".join(lines[i:j]))
                i = j
        else:
            raise AdapterError(
                f"{path.name}: unrecognized top-level line: {stripped[:80]}")

    if theorem_start is None:
        raise AdapterError(f"{path.name}: no theorem found")
    thm_block = "\n".join(lines[theorem_start:]).strip()
    m = _THEOREM_RE.match(thm_block)
    if m is None:
        raise AdapterError(f"{path.name}: theorem block does not match "
                           f"`theorem <name> <sig> := sorry`")
    name = m.group(1).strip()
    raw_sig = m.group(2).strip()  # newlines preserved — see
    if not raw_sig:               # _normalize_signature docstring
        raise AdapterError(f"{path.name}: empty theorem signature")
    return ProblemSpec(
        name=name, signature=_normalize_signature(raw_sig), opens=opens,
        set_options=set_options, decls=decls, informal=informal,
        solution_name=solution_name, source_file=path,
    )


# ---------------------------------------------------------------------
# emission
# ---------------------------------------------------------------------

def _header(spec: ProblemSpec, *, import_defs: bool) -> str:
    out = "import Mathlib\n"
    if import_defs:
        out += f"import Problems.{spec.slug}.Defs\n"
    out += "\n"
    # Workspace-side lint hygiene, NOT a statement edit: the one-line
    # statement form trips the longLine style linter, and lint noise
    # buries real errors in agent-facing build output.
    out += "set_option linter.style.longLine false\n\n"
    for clause in spec.set_options:
        out += f"set_option {clause}\n"
    if spec.set_options:
        out += "\n"
    for clause in spec.opens:
        out += f"open {clause}\n"
    if spec.opens:
        out += "\n"
    return out


def _defs_lean(spec: ProblemSpec) -> str:
    body = _header(spec, import_defs=False)
    body += f"namespace Problems.{spec.slug}\n\n"
    for decl in spec.decls:
        body += decl + "\n\n"
    body += f"end Problems.{spec.slug}\n"
    return body


def _root_lean(spec: ProblemSpec) -> str:
    body = _header(spec, import_defs=True)
    body += (
        f"namespace Problems.{spec.slug}\n"
        f"\n"
        f"theorem main : {spec.signature} := by sorry\n"
        f"\n"
        f"end Problems.{spec.slug}\n"
    )
    return body


def _problem_seed(spec: ProblemSpec, *, upstream_commit: str = "") -> str:
    """problem.json seed content (v40 — Manifest.md retired: the
    charter is the informal statement, machine settings ride the
    `settings` block; `signoff: false` = unattended batch protocol)."""
    year, slot = "", ""
    if m := re.fullmatch(r'putnam_(\d{4})_([ab]\d)', spec.name):
        year, slot = m.group(1), m.group(2).upper()
    defs_note = (
        "The `_solution` abbrev in `Defs.lean` carries the OFFICIAL\n"
        "answer (upstream ships it as a comment; this matches the\n"
        "standard solutions-replaced evaluation protocol — the task\n"
        "is proving, not answer-finding).\n"
        if spec.solution_name else
        "No solution abbrev — pure proof task.\n"
    )
    provenance = "trishullab/PutnamBench"
    if upstream_commit:
        provenance += f" @ {upstream_commit}"
    charter = (
        f"# {spec.slug} — imported from PutnamBench\n"
        f"\n"
        f"Original theorem: `{spec.name}` (Putnam {year} {slot}).\n"
        f"\n"
        f"{spec.informal}\n"
        f"\n"
        f"The formal statement is pinned in `Root.lean` (`theorem main`).\n"
        f"{defs_note}"
        f"\n"
        f"Imported via `Benchmarks/putnambench/adapter.py` from\n"
        f"{provenance}. No per-problem hints —\n"
        f"benchmark integrity. The pinned statement is never edited;\n"
        f"if you believe it is FALSE, that is what "
        f"`RequestUserAmend` is for.\n"
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


def emit_problem_dir(spec: ProblemSpec, output_root: Path, *,
                     upstream_commit: str = "") -> Path:
    """Materialize Problems/Putnam/<name>/{problem.json, Defs.lean,
    Root.lean}. Idempotent overwrite of these three files; never
    touches proofs/ (owned by the framework after init)."""
    pdir = output_root / spec.rel_dir
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Defs.lean").write_text(_defs_lean(spec), encoding="utf-8")
    (pdir / "Root.lean").write_text(_root_lean(spec), encoding="utf-8")
    (pdir / "problem.json").write_text(
        _problem_seed(spec, upstream_commit=upstream_commit),
        encoding="utf-8")
    return pdir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert PutnamBench Lean 4 problems to Asterism "
                    "Problem dirs.")
    parser.add_argument(
        "--source", type=Path, required=True,
        help="PutnamBench lean4/src directory")
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Asterism Problems/ root")
    parser.add_argument(
        "--names", type=str, default=None,
        help="Comma-separated original names (e.g. putnam_1962_a1). "
             "Default: all files.")
    parser.add_argument("--upstream-commit", type=str, default="")
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print(f"FAIL: {args.source} is not a directory", file=sys.stderr)
        return 1
    wanted = ({s.strip() for s in args.names.split(",")}
              if args.names else None)
    imported, failed = [], []
    for p in sorted(args.source.glob("*.lean")):
        if wanted is not None and p.stem not in wanted:
            continue
        try:
            spec = parse_problem_file(p)
            emit_problem_dir(spec, args.output,
                             upstream_commit=args.upstream_commit)
            imported.append(spec.slug)
        except AdapterError as e:
            failed.append(str(e))
    print(f"Imported {len(imported)} problem(s).")
    for s in imported[:10]:
        print(f"  {s}")
    if len(imported) > 10:
        print(f"  ... ({len(imported) - 10} more)")
    if failed:
        print(f"\n{len(failed)} file(s) failed to parse:")
        for msg in failed:
            print(f"  {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
