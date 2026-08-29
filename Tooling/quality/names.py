"""Top-level declaration names as a STRING gate (owner ruling 2026-08-29).

Every file that lands under a problem — a Forward brick, a Backward
stub, a `_strategy_s*.lean` scratch — declares its helpers in the
problem namespace, next to every other file's. Two files that each
carry a private copy of the same helper build fine alone and refuse to
share an environment (`environment already contains`), which is how the
dedupe probe went blind on 2026-08-29 (8 of 10 batches refused; eight
such names on disk, every one involving a shelved leftover).

This module answers the cheap question before the kernel is asked
anything: *does this text declare a top-level name some other file of
the problem already declares?* The gate runs at the two landing doors
(`forward.commit_forward_lemma`, `backward._place_unowned`) and is
mirrored at validate time so the agent hears it while it can still act.
A collision is refused with both ways out named; the framework's own
generated slugs keep their auto-suffix (`backward._resolve_slug_collisions`).

Deliberately a text scan, not an elaboration: it must be free to run on
every validate call and it must work on a file that does not build yet.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

#: Column-0 declarations only. Modifiers and inline attributes may
#: precede the keyword; `private` names are file-local in Lean 4 and
#: cannot collide, so they are dropped below. An anonymous `instance :`
#: has no name token after the keyword and does not match.
_DECL_RE = re.compile(
    r"^(?:@\[[^\]]*\]\s*)*"
    r"(?P<mods>(?:(?:private|protected|noncomputable|unsafe|partial|nonrec)\s+)*)"
    r"(?P<kind>theorem|lemma|def|abbrev|structure|class|inductive|instance|opaque|axiom)"
    r"\s+(?P<name>[A-Za-z_][\w'.!?]*)")
_NAMESPACE_RE = re.compile(r"^namespace\s+(\S+)")
_SECTION_RE = re.compile(r"^section\b")
_END_RE = re.compile(r"^end\b")

#: Files whose names share the problem namespace with the bricks.
_PROBLEM_LEVEL_FILES = ("Defs.lean", "Root.lean")


def _strip_comments(text: str) -> list[str]:
    """Lines with `--` and `/- … -/` comment text blanked, line count
    preserved (so reported line numbers stay the file's)."""
    out: list[str] = []
    in_block = 0
    for raw in text.splitlines():
        buf = []
        i = 0
        while i < len(raw):
            two = raw[i:i + 2]
            if in_block:
                if two == "-/":
                    in_block -= 1
                    i += 2
                elif two == "/-":
                    in_block += 1
                    i += 2
                else:
                    i += 1
                continue
            if two == "/-":
                in_block += 1
                i += 2
            elif two == "--":
                break
            else:
                buf.append(raw[i])
                i += 1
        out.append("".join(buf))
    return out


def top_level_names(text: str) -> list[tuple[str, str, int]]:
    """`[(qualified_name, kind, line)]` for every column-0 declaration,
    qualified by the enclosing `namespace` blocks (sections add no
    prefix). `private` declarations are omitted."""
    names: list[tuple[str, str, int]] = []
    stack: list[str | None] = []      # None = section frame
    pending_attr = False
    for ln, line in enumerate(_strip_comments(text), start=1):
        if not line or line[0].isspace():
            continue
        m = _NAMESPACE_RE.match(line)
        if m:
            stack.append(m.group(1))
            continue
        if _SECTION_RE.match(line):
            stack.append(None)
            continue
        if _END_RE.match(line):
            if stack:
                stack.pop()
            continue
        stripped = line.strip()
        if stripped.startswith("@[") and stripped.endswith("]"):
            pending_attr = True
            continue
        m = _DECL_RE.match(line)
        pending_attr = False
        if not m:
            continue
        if "private" in m.group("mods").split():
            continue
        prefix = ".".join(p for p in stack if p)
        name = m.group("name")
        names.append((f"{prefix}.{name}" if prefix else name,
                      m.group("kind"), ln))
    del pending_attr
    return names


_INDEX_CACHE: dict[tuple[str, int, int], list[tuple[str, str, int]]] = {}


def _names_of(path: Path) -> list[tuple[str, str, int]]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _INDEX_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    got = top_level_names(text)
    _INDEX_CACHE[key] = got
    return got


def name_index(problem_dir: Path) -> dict[str, str]:
    """`qualified_name → problem-relative posix path` over `proofs/*.lean`
    plus the problem-level files. When several files already declare the
    same name (the residue this gate exists to stop growing), the first
    in sorted order is kept — reporting that residue is a sweep's job,
    not the landing gate's."""
    files: list[Path] = []
    proofs = problem_dir / "proofs"
    if proofs.is_dir():
        with os.scandir(proofs) as it:
            files.extend(Path(e.path) for e in it
                         if e.name.endswith(".lean") and e.is_file())
    for fn in _PROBLEM_LEVEL_FILES:
        p = problem_dir / fn
        if p.is_file():
            files.append(p)
    index: dict[str, str] = {}
    for path in sorted(files):
        rel = path.relative_to(problem_dir).as_posix()
        for name, _kind, _ln in _names_of(path):
            index.setdefault(name, rel)
    return index


@dataclass(frozen=True)
class Collision:
    name: str
    existing: str      # problem-relative path of the file that owns it
    line: int          # line in the candidate text


def collisions(problem_dir: Path, text: str, *,
               own_rel: "str | None") -> list[Collision]:
    """Names in `text` that some OTHER file of the problem already
    declares. `own_rel` is the candidate's own problem-relative path
    (a re-landed brick is not in collision with itself)."""
    index = name_index(problem_dir)
    hits: list[Collision] = []
    for name, _kind, ln in top_level_names(text):
        owner = index.get(name)
        if owner is None or owner == own_rel:
            continue
        hits.append(Collision(name=name, existing=owner, line=ln))
    return hits


def teaching(hits: list[Collision]) -> str:
    """The way out, named: cite the existing declaration, or rename a
    genuinely different concept. Never a silent `_2` — two private
    copies of one helper is exactly the duplication dedupe exists to
    catch, and a copy that differs is a bug hiding behind a name."""
    lines = ["Top-level name collision — this file re-declares a name "
             "another file of this problem already declares:"]
    for h in hits:
        short = h.name.rsplit(".", 1)[-1]
        lines.append(f"  - `{short}` (line {h.line}) is already declared "
                     f"in {h.existing}")
    lines.append(
        "Do one of: CITE the existing declaration (import its module and "
        "use it, do not redefine it), or — if yours is a different "
        "concept — RENAME yours to something that says how it differs. "
        "The file cannot land while a name is doubled: two copies cannot "
        "be imported together, and every later consumer of both would "
        "fail at `environment already contains`.")
    return "\n".join(lines)


class NameCollision(Exception):
    """Raised at a landing door. `str()` is the teaching message."""

    def __init__(self, hits: list[Collision]):
        self.hits = hits
        super().__init__(teaching(hits))


def problem_dir_of(landing_path: Path) -> Path:
    """The problem directory a landing path belongs to (`proofs/<f>` or a
    problem-level file)."""
    p = landing_path.parent
    return p.parent if p.name == "proofs" else p


def check_landing_at(dst: Path, text: str) -> None:
    """The gate at a landing door: raise `NameCollision` or return."""
    pdir = problem_dir_of(dst)
    hits = collisions(pdir, text, own_rel=dst.relative_to(pdir).as_posix())
    if hits:
        raise NameCollision(hits)


def submission(text: str, problem_dir: Path, *,
               own_rel: "str | None") -> "dict | None":
    """The validate-time mirror: a `submission.names` block when the
    commit door would refuse, else None (the block is absent when clean,
    like the other submission gates)."""
    hits = collisions(problem_dir, text, own_rel=own_rel)
    if not hits:
        return None
    return {
        "ok": False,
        "collisions": [{"name": h.name, "existing": h.existing,
                        "line": h.line} for h in hits],
        "teaching": teaching(hits),
    }
