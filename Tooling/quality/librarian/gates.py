"""Librarian gates — deterministic framework-side checks.

These are the *mechanical judges* of the Librarian pipeline (plan §2).
The Librarian agent proposes Library files; these gates accept or reject
them without any judgement of their own.

Gate A — import-closure (this module, M2)
    Every Library file's `import` set must be a subset of
    {Mathlib.*, Library.*}. A Library that imports `Problems.*` or a
    problem's `Defs` is not self-contained — it still depends on the
    framework's per-problem scaffolding and could never be upstreamed
    (plan §1 north star).

Gate B — root re-derivation (M3, separate function below — stub for now)

The pure-text closure check is the authoritative fast gate. An optional
`build_verify=True` additionally runs the gateway lake build (the same
`gateway_lifecycle.verify_file` the proof pipelines use) to confirm the
file actually elaborates against only Mathlib + Library — catching a
file that passes the text check but references a Problems symbol via
`open`/full-qualification without an explicit import.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# Matches a Lean import line, tolerating the newer `public import` /
# `private import` module-system prefixes mathlib now emits. Captures the
# dotted module path.
_IMPORT_RE = re.compile(
    r"^\s*(?:public\s+|private\s+)?import\s+([A-Za-z_][\w.]*)\s*$"
)

# Roots a self-contained Library file is allowed to import.
_ALLOWED_ROOTS = ("Mathlib", "Library", "Init", "Std", "Batteries", "Lean")


@dataclass
class GateResult:
    ok: bool
    issues: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def parse_imports(text: str) -> list[str]:
    """Return the dotted module paths imported by a Lean source string,
    in order. Ignores comments-only and non-import lines."""
    out: list[str] = []
    for line in text.splitlines():
        m = _IMPORT_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def _root_of(module: str) -> str:
    return module.split(".", 1)[0]


def check_import_closure_text(text: str, *, label: str = "<file>") -> GateResult:
    """Gate A core (pure text): assert every import's root is in
    `_ALLOWED_ROOTS`. Any `Problems.*` (or anything else outside the
    allow-list) is a violation."""
    issues: list[str] = []
    for mod in parse_imports(text):
        root = _root_of(mod)
        if root not in _ALLOWED_ROOTS:
            issues.append(f"{label}: forbidden import `{mod}` "
                          f"(root `{root}` not in {list(_ALLOWED_ROOTS)})")
    return GateResult(not issues, issues)


def check_import_closure(
    path: Path, *, build_verify: bool = False,
    workspace: Path | None = None,
) -> GateResult:
    """Gate A for a file on disk. Pure-text closure check always runs;
    `build_verify=True` additionally runs the gateway lake build to
    catch un-imported cross-references (slow — opt in)."""
    if not path.exists():
        return GateResult(False, [f"{path}: file does not exist"])
    text = path.read_text(encoding="utf-8", errors="replace")
    res = check_import_closure_text(text, label=path.name)
    if not res.ok or not build_verify:
        return res
    # Text check passed and caller wants the authoritative build.
    from ...lsp import lifecycle as gateway_lifecycle
    ok, err = gateway_lifecycle.verify_file(
        path, write_olean=False, workspace=workspace)
    if not ok:
        return GateResult(False, [f"{path.name}: build-verify failed "
                                  f"({err})"])
    return GateResult(True, [])


def check_dir_import_closure(
    directory: Path, *, build_verify: bool = False,
    workspace: Path | None = None,
) -> GateResult:
    """Run Gate A over every `.lean` file under `directory`. Aggregates
    all issues so the operator sees the full violation set at once."""
    issues: list[str] = []
    for f in sorted(directory.rglob("*.lean")):
        r = check_import_closure(
            f, build_verify=build_verify, workspace=workspace)
        issues.extend(r.issues)
    return GateResult(not issues, issues)
