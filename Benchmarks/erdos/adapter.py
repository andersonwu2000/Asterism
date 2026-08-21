"""formal-conjectures Erdős problems → Asterism Problem dirs.

Converts google-deepmind/formal-conjectures `ErdosProblems/<n>.lean`
statements into `Problems/Erdos/p<n>/` dirs (problem.json + Defs.lean),
mirroring the miniF2F adapter's shapes (`cmd_init` writes Root.lean from
the charter's ## Statement).

v1 corpus policy — a file is imported iff it contains a DIRECT open
conjecture: a `theorem` tagged `@[category research open ...]` whose
statement does not use the `answer(...)` elaborator. `answer(sorry) ↔ P`
decls are open QUESTIONS (truth value unknown) — a hard Root pins the
prove direction only, so they are out of scope for v1 (78/610 files
qualify, measured 2026-08-21).

Context carried into Defs.lean:
  - the source file's top-level `open` / `open scoped` lines (their
    notation surface);
  - every top-level helper `def` / `abbrev` / `noncomputable def`
    declared BEFORE the chosen theorem (many statements reference
    file-local predicates). Helpers keep their docstrings; attributes
    are stripped.

Toolchain drift: formal-conjectures pins v4.27.0, this workspace runs
v4.30.0-rc2 — every emitted problem must pass the elaboration screen
(`screen.py`) before entering a run; failures are deleted by default.

Provenance: statements © The Formal Conjectures Authors, Apache-2.0.
Reference URLs (erdosproblems.com/<n>) are kept in each charter.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "minif2f"))
from adapter import _normalize_signature  # noqa: E402  (shared fold logic)

ATTR_RE = re.compile(
    r"(?:/--(?P<doc>(?:(?!-/)[\s\S])*)-/\s*)?"
    r"@\[(?P<attrs>category research open[^\]]*)\]\s*\n"
    r"(?P<decl>theorem\s+(?P<name>[\w.]+)(?P<sig>[\s\S]*?))"
    r":=\s*(?:by\s*\n\s*sorry|sorry)")
MODULE_DOC_RE = re.compile(r"/-!([\s\S]*?)-/")
OPEN_RE = re.compile(r"^open\s.*$", re.MULTILINE)
HELPER_RE = re.compile(
    r"(?:/--[\s\S]*?-/\s*)?(?:@\[[^\]]*\]\s*)?"
    r"(?:noncomputable\s+)?(?:def|abbrev)\s+\w+[\s\S]*?"
    r"(?=\n\n|\n/-|\n@\[|\ntheorem|\nend )")


@dataclass
class ErdosSpec:
    number: str
    name: str
    statement: str            # normalized ∀-form
    module_doc: str
    decl_doc: str
    ams: str
    opens: list[str] = field(default_factory=list)
    helpers: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return f"Erdos.p{self.number}"


def _preamble_decls(text: str, upto: int) -> list[str]:
    """Every top-level NON-theorem declaration before offset `upto`,
    with its docstring, minus imports / namespace lines / category
    attributes. Theorems (solved variants carry `sorry` bodies) are
    dropped — Defs.lean must stay sorry-free."""
    region = text[:upto]
    # cut everything through the module docstring and imports
    m = MODULE_DOC_RE.search(region)
    start = m.end() if m else 0
    blocks, cur = [], []
    keep_kw = re.compile(
        r"^(noncomputable\s+)?(def|abbrev|instance|structure|"
        r"inductive|notation|scoped notation|class)[\s\[({]")
    drop_line = re.compile(r"^(import\s|namespace\s|end\s|open\s|@\[category)")
    _SPLIT = (chr(10) + r'(?=/--|@\[|noncomputable |def |abbrev |instance |' + r'structure |inductive |notation |theorem |lemma |namespace |end |open )')
    for chunk in re.split(_SPLIT, region[start:]):
        body = chunk.strip()
        if not body or drop_line.match(body):
            continue
        # peel docstring/attrs to find the decl keyword
        head = re.sub(r"^(/--[\s\S]*?-/\s*)?(@\[[^\]]*\]\s*)*", "", body)
        if keep_kw.match(head):
            blocks.append(body)
    return blocks


def parse_file(path: Path) -> "ErdosSpec | None":
    text = path.read_text(encoding="utf-8")
    candidates = [m for m in ATTR_RE.finditer(text)
                  if "answer(" not in m.group("decl")]
    if not candidates:
        return None
    plain = [m for m in candidates if "." not in m.group("name")]
    chosen = plain[0] if plain else candidates[0]
    sig = chosen.group("sig").strip()
    mdoc = MODULE_DOC_RE.search(text)
    ams = ""
    am = re.search(r"AMS\s+([\d\s]+)", chosen.group("attrs"))
    if am:
        ams = am.group(1).strip()
    helpers = _preamble_decls(text, chosen.start())
    opens = [ln.strip() for ln in OPEN_RE.findall(text)
             if not ln.strip().endswith(" in")]
    return ErdosSpec(
        number=path.stem, name=chosen.group("name"),
        statement=_normalize_signature(sig),
        module_doc=(mdoc.group(1).strip() if mdoc else ""),
        decl_doc=(chosen.group("doc") or "").strip(),
        ams=ams, opens=opens, helpers=helpers)


def _charter(spec: ErdosSpec) -> str:
    parts = [
        f"# {spec.slug} — Erdős problem {spec.number}",
        "",
        f"Reference: https://www.erdosproblems.com/{spec.number}",
        f"Imported from google-deepmind/formal-conjectures"
        f" (`ErdosProblems/{spec.number}.lean`, theorem `{spec.name}`,"
        f" AMS {spec.ams or '?'}).",
        "",
        spec.decl_doc or spec.module_doc,
        "",
        "## Statement",
        spec.statement,
        "",
        "## Strategic notes",
        "Open conjecture — prove-or-refute posture applies to sub-claims,",
        "but the root asserts the conjectured statement itself. No",
        "per-problem hints (benchmark integrity).",
    ]
    return "\n".join(parts) + "\n"


def _defs(spec: ErdosSpec) -> str:
    lines = ["import Mathlib", "", "set_option maxHeartbeats 400000", ""]
    lines += spec.opens + [""] if spec.opens else []
    lines += [f"namespace Problems.Erdos.p{spec.number}", ""]
    for h in spec.helpers:
        lines += [h, ""]
    lines += [f"end Problems.Erdos.p{spec.number}", ""]
    return "\n".join(lines)


def emit(spec: ErdosSpec, problems_root: Path) -> Path:
    pdir = problems_root / "Erdos" / f"p{spec.number}"
    pdir.mkdir(parents=True, exist_ok=True)
    seed = {
        "problem": spec.slug,
        "charter": _charter(spec),
        "settings": {
            "axioms_whitelist": ["propext", "Quot.sound",
                                 "Classical.choice"],
            "forbidden_lemmas": [],
            "library": False,
            "signoff": False,
        },
    }
    (pdir / "problem.json").write_text(
        json.dumps(seed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (pdir / "Defs.lean").write_text(_defs(spec), encoding="utf-8")
    return pdir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True,
                    help="formal-conjectures/FormalConjectures/ErdosProblems")
    ap.add_argument("--problems-root", type=Path, required=True)
    ap.add_argument("--only", nargs="*", default=None,
                    help="problem numbers to import (default: all direct)")
    args = ap.parse_args()
    done, skipped = [], []
    for f in sorted(args.source.glob("*.lean"),
                    key=lambda p: int(re.sub(r"\D", "", p.stem) or 0)):
        if args.only and f.stem not in args.only:
            continue
        spec = parse_file(f)
        if spec is None:
            skipped.append(f.stem)
            continue
        emit(spec, args.problems_root)
        done.append(spec.number)
    print(f"imported {len(done)}: {','.join(done[:20])}"
          f"{'...' if len(done) > 20 else ''}")
    print(f"skipped (no direct open theorem): {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
