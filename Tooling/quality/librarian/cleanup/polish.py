"""§13 (e) polish stage — one agentic, type-preserving whole-file rewrite."""
from __future__ import annotations

import re
from pathlib import Path

from . import _common as C
from ._common import _Decl


# ---------------------------------------------------------------------
# §13 (e) polish — one agentic, type-PRESERVING whole-file rewrite that merges
# variable-extraction + docstrings + module docstring + mathlib style + local
# (type-preserving) warning cleanup. Surface conformance only; semantic idiom
# alignment is the separate `audit` stage, and name/signature changes are
# `rename` / `unused_args` (type-CHANGING, consumer-impacting). Gate = build +
# every decl's elaborated type unchanged (#check, the silent-statement-drift
# guard) + clearable warnings reduced (retry feeding the residual warnings).
# ---------------------------------------------------------------------

_POLISH_PROMPT = "polish.md"
_POLISH_OUTPUT = "polished.lean"
_POLISH_MAX_RETRIES = 2
# The warnings polish OWNS — type-preserving + local. `dupNamespace` (a naming /
# namespace issue) and `unusedArguments` (signature-changing → consumer impact)
# are audit / decide's job, never touched here.
_POLISH_WARN_RE = re.compile(
    r"warning:.*?(unused variable|exceeds the \d+ character|"
    r"linter\.style|unnecessary)", re.I)


def _polish_warnings(build_output: str) -> "list[str]":
    """The clearable, type-preserving warnings polish is responsible for."""
    return [m.group(0)[:160] for m in _POLISH_WARN_RE.finditer(build_output)]


def _polish_context(workspace: Path, problem: str, rel: str,
                    decl_names: "list[str]", prev_error: str = "") -> str:
    """Per-file context for the polish agent: module, declarations, the verbatim
    file, and (on retry) the failure / residual warnings to fix."""
    try:
        body = (workspace / rel).read_text(encoding="utf-8")
    except OSError:
        body = ""
    lines = [
        f"# PR-style polish — {problem} — `{rel}`", "",
        f"Module: `{C._mod_of_rel(rel)}`.",
        f"Declarations: {', '.join(decl_names) or '(none)'}", "",
        "## Current file", "", "```lean", body.rstrip(), "```", "",
    ]
    if prev_error:
        lines += ["## Fix these and re-emit", "", "```", prev_error[-1800:],
                  "```", ""]
    return "\n".join(lines) + "\n"


def file_cleanup_polish(workspace: Path, problem: str, target_file: str,
                        decls_in_file: "list[_Decl]", *,
                        max_retries: int = _POLISH_MAX_RETRIES) -> bool:
    """§13 (e) PR-style polish for ONE file — merges variable-extraction +
    docstrings + module docstring + mathlib style + local warning cleanup into a
    single agentic, TYPE-PRESERVING whole-file rewrite. Snapshot decl types →
    spawn → gate (builds AND every decl's elaborated type unchanged) → if
    clearable warnings remain, retry feeding them; on a type/build failure retry
    feeding the error. Keep the best green + type-safe version (fewest warnings),
    else the original. Returns whether the file changed.

    Type-preserving by contract: the #check snapshot rejects any silent statement
    change an LLM might slip into a free-form rewrite (the #91 blind-rewrite
    guard) — style/comments/structure may change, types never."""
    prompt_path = workspace / "Tooling" / "prompts" / "librarian" / _POLISH_PROMPT
    if not prompt_path.exists() or not decls_in_file:
        return False
    leaf = target_file.split("/")[-1]
    try:
        original = (workspace / target_file).read_text(encoding="utf-8")
    except OSError:
        return False
    fqns = [d.fqn for d in decls_in_file]
    ok0, _d0, base_types = C._typecheck_capturing_types(workspace, original, fqns)
    if not ok0:
        print(f"[staged] polish `{leaf}` — skip (no type snapshot)", flush=True)
        return False
    decl_names = [d.name for d in decls_in_file]
    prev_error = ""
    best: "tuple[int, str] | None" = None       # (warning count, text)
    for attempt in range(max_retries + 1):
        got = C.spawn_collect(
            workspace, problem, prompt_path,
            _polish_context(workspace, problem, target_file, decl_names,
                            prev_error),
            [_POLISH_OUTPUT])
        if got is None:
            prev_error = f"no {_POLISH_OUTPUT} was produced"
            continue
        new_text = got[_POLISH_OUTPUT]
        if new_text.strip() == original.strip():
            return False                          # already idiomatic — clean no-op
        ok, detail, new_types = C._typecheck_capturing_types(
            workspace, new_text, fqns)
        if not ok:
            prev_error = detail
            continue
        changed = [f for f in fqns if base_types.get(f) != new_types.get(f)]
        if changed:
            prev_error = ("the elaborated type changed for: "
                          + ", ".join(f.rsplit(".", 1)[-1] for f in changed)
                          + " — polish spelling/comments/style, NEVER the type")
            continue
        warns = _polish_warnings(
            C._build_with_output(workspace, new_text, prefix="_polish_warn")[1])
        if best is None or len(warns) < best[0]:
            best = (len(warns), new_text)
        if not warns:
            break                                 # clean — done
        prev_error = ("the rewrite still builds + types match, but these "
                      "warnings remain — clear them:\n" + "\n".join(warns[:10]))
    if best is None:
        print(f"[staged] polish `{leaf}` — kept original "
              f"(no green polish in {max_retries + 1} tries)", flush=True)
        return False
    n_warn, text = best
    (workspace / target_file).write_text(text, encoding="utf-8")
    print(f"[staged] polish `{leaf}` — applied ({n_warn} residual warning(s))",
          flush=True)
    return True
