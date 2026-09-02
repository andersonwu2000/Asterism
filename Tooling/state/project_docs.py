"""state.project_docs — the Project's document root (HID §3.6).

`Problems/<project>/_docs/` is the one place in the tree a person and
the Assistant may both write, and the only place either of them writes
at all. Two sub-roots, and the split is the mechanism §1.1's capability
matrix is made of:

  _docs/user/    the person's own writing, reached through the console
  _docs/agent/   what the Assistant produced, reached through its one
                 write tool (`write_project_doc`)

`_docs` leads with an underscore on purpose: `projects.NAME_RE` refuses
it, so no problem directory can ever be called that and the docs root
cannot collide with a sibling problem (§3.6). Everything that walks
`Problems/` looking for problems has to skip it for the same reason —
`ROOT_DIRNAME` is the one spelling those walks import.

REFUSALS. Every path arrives from an HTTP request or from a model, so
this module treats the string as hostile and answers in the two types
`state/projects.py` established: `KeyError` = the named thing is not
there (404 upstream), `ValueError` = it is refused (422). A refusal
message names the way out — a model that is told only "no" invents an
action that passes the check instead (memory:
`gate_must_name_a_reachable_action`).

The fence is three checks, not one, because a path can leave the root
three ways: the string (`..`, an absolute path, a drive letter), the
filesystem (a symlink or junction planted inside the root), and the
name (an extension nobody wants written into a document tree). The
first is normalisation, the second is `realpath` on the resolved
target, and the third is the whitelist below.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import projects as _projects

#: The docs root's directory name, under `Problems/<project>/`.
ROOT_DIRNAME = "_docs"

AREA_USER = "user"
AREA_AGENT = "agent"
#: The two sub-roots. A docs path names its area first, always: with no
#: area the path would be ambiguous exactly where the write fence lives.
AREAS: "tuple[str, ...]" = (AREA_USER, AREA_AGENT)

#: §3.6's extension whitelist. Enforced on WRITE — that is what makes it
#: a property of the tree rather than a filter on the way out.
EXTENSIONS: "frozenset[str]" = frozenset({
    ".md", ".tex", ".txt", ".lean", ".png", ".jpg", ".svg", ".pdf"})

#: Which of those cannot be handed to the browser as text (`.svg` can —
#: it is XML). The API base64s these; nothing here decodes anything.
BINARY_EXTENSIONS: "frozenset[str]" = frozenset({".png", ".jpg", ".pdf"})


def root(workspace: Path, project: str) -> Path:
    """`<workspace>/Problems/<project>/_docs`.

    The project name is validated HERE rather than by the caller: it is
    a path component, and a caller that forgets is a caller that wrote
    `../../` into the tree.
    """
    name = (project or "").strip()
    if not _projects.NAME_RE.fullmatch(name):
        raise _projects.InvalidName(
            f"invalid project name {project!r} — one identifier "
            f"(letter, then letters/digits/underscore)")
    return Path(workspace) / "Problems" / name / ROOT_DIRNAME


# ---------------------------------------------------------------------
# the fence
# ---------------------------------------------------------------------

def _relative(path: str, area: "str | None") -> PurePosixPath:
    """The request's path as a clean root-relative posix path.

    `area`, when given, is the only area this call may touch — the write
    fence, and the reason `write(area='agent')` cannot reach `user/`.
    """
    raw = str(path or "").strip().replace("\\", "/").strip("/")
    hint = f"{area or AREA_USER}/<name>.md"
    if not raw:
        raise ValueError(
            f"a document path is required, relative to the Project's "
            f"docs root and starting with an area — e.g. {hint}")
    if PureWindowsPath(str(path)).is_absolute() or str(path).startswith("/"):
        raise ValueError(
            f"{path!r} is an absolute path; documents are addressed "
            f"relative to the Project's docs root — e.g. {hint}")
    parts = [p for p in PurePosixPath(raw).parts if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(
            f"{path!r} climbs out of the Project's docs root, which is "
            f"the whole tree these documents may live in — write it "
            f"under {area or AREA_USER}/ instead")
    if not parts:
        raise ValueError(f"a document path is required — e.g. {hint}")
    if parts[0] not in AREAS:
        # Not a typo to correct silently: `user/` and `agent/` are
        # different owners, and guessing one would be the write fence
        # guessing on the caller's behalf.
        raise ValueError(
            f"a document path starts with its area — {' or '.join(AREAS)}"
            f". Did you mean {area or AREA_USER}/{raw}?")
    if area is not None and parts[0] != area:
        raise ValueError(
            f"this call may only write under {area}/ — {raw!r} is in "
            f"{parts[0]}/. Write it to {area}/{'/'.join(parts[1:])} "
            f"instead.")
    return PurePosixPath(*parts)


def _resolve(workspace: Path, project: str, path: str, *,
             area: "str | None" = None) -> "tuple[Path, PurePosixPath]":
    """(absolute target, root-relative path), fenced.

    The second check lives here: `realpath` resolves every symlink and
    junction along the existing part of the path, so a link planted
    inside the root cannot smuggle the target outside it. Normalising
    the string alone would pass that — the escape that survives
    normalisation is a link, which is why §3.6 names it separately.
    """
    base = root(workspace, project)
    rel = _relative(path, area)
    target = base / Path(*rel.parts)
    real_root = Path(os.path.realpath(base))
    real_target = Path(os.path.realpath(target))
    if real_target != real_root and real_root not in real_target.parents:
        raise ValueError(
            f"{path!r} resolves outside the Project's docs root (a link "
            f"or junction leads out of it) — write to a plain path "
            f"under {area or AREA_USER}/ instead")
    return target, rel


def _check_extension(rel: PurePosixPath) -> None:
    if rel.suffix.lower() not in EXTENSIONS:
        raise ValueError(
            f"{rel.name!r} is not a document — this tree takes "
            f"{' '.join(sorted(EXTENSIONS))}. Rename it with one of "
            f"those extensions.")


def is_binary(path: str) -> bool:
    """Whether `read` should be handed to the caller as bytes."""
    return PurePosixPath(str(path)).suffix.lower() in BINARY_EXTENSIONS


# ---------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------

def tree(workspace: Path, project: str) -> "list[dict]":
    """Every entry under the docs root, directories included, sorted.

    Flat and root-relative, because the left rail draws the nesting from
    the paths and a nested payload would make "which file is open" a
    walk instead of a string. A Project with no docs yet has an empty
    tree, not an error: the root is created by the first write.
    """
    base = root(workspace, project)
    if not base.is_dir():
        return []
    out: "list[dict]" = []
    # followlinks=False: a link inside the root would otherwise let the
    # listing walk (and, on a cycle, never finish) outside it.
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        here = Path(dirpath)
        dirnames.sort()
        for name in dirnames:
            rel = (here / name).relative_to(base).as_posix()
            out.append({"path": rel, "kind": "dir"})
        for name in sorted(filenames):
            p = here / name
            rel = p.relative_to(base).as_posix()
            try:
                size = p.stat().st_size
            except OSError:  # pragma: no cover — raced deletion
                continue
            out.append({"path": rel, "kind": "file", "size": int(size)})
    out.sort(key=lambda e: e["path"])
    return out


def read(workspace: Path, project: str, path: str) -> bytes:
    """The file's bytes. Text or not is the caller's decision to make
    from `is_binary` — this layer does not guess an encoding."""
    target, _rel = _resolve(workspace, project, path)
    if not target.is_file():
        raise KeyError(path)
    return target.read_bytes()


# ---------------------------------------------------------------------
# writes
# ---------------------------------------------------------------------

def write(workspace: Path, project: str, path: str,
          content: "str | bytes", *, area: str = AREA_USER) -> str:
    """Write one document; returns its root-relative path.

    `area` is the fence, not a default to be trusted: the console passes
    `user`, the Assistant's tool passes `agent`, and a path in the other
    area is REFUSED rather than rewritten. Parent folders are created —
    a person naming a chapter folder in the path means to have one.
    """
    if area not in AREAS:
        raise ValueError(f"unknown docs area {area!r}; "
                         f"expected one of {' '.join(AREAS)}")
    target, rel = _resolve(workspace, project, path, area=area)
    _check_extension(rel)
    if target.is_dir():
        raise ValueError(f"{rel.as_posix()!r} is a folder — name a file "
                         f"inside it instead")
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        # newline="" — no line-ending translation. A document written
        # through the console and read back by a tool (or diffed, or
        # hashed) must be the same bytes; Windows' default would turn
        # every `\n` the editor sent into `\r\n` on the way to disk.
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
    else:
        target.write_bytes(content)
    return rel.as_posix()


def mkdir(workspace: Path, project: str, path: str, *,
          area: str = AREA_USER) -> str:
    """Create a folder (and its parents). Idempotent."""
    if area not in AREAS:
        raise ValueError(f"unknown docs area {area!r}; "
                         f"expected one of {' '.join(AREAS)}")
    target, rel = _resolve(workspace, project, path, area=area)
    if target.is_file():
        raise ValueError(f"{rel.as_posix()!r} is a file, not a folder")
    target.mkdir(parents=True, exist_ok=True)
    return rel.as_posix()


def delete(workspace: Path, project: str, path: str, *,
           area: str = AREA_USER) -> str:
    """Remove one document, or one EMPTY folder.

    A recursive delete is deliberately absent: one click must not be
    able to take a tree with it, and the person who means to can empty
    the folder first. The refusal names what is still inside.
    """
    if area not in AREAS:
        raise ValueError(f"unknown docs area {area!r}; "
                         f"expected one of {' '.join(AREAS)}")
    target, rel = _resolve(workspace, project, path, area=area)
    if not target.exists():
        raise KeyError(path)
    if target.is_dir():
        kids = sorted(p.name for p in target.iterdir())
        if kids:
            raise ValueError(
                f"{rel.as_posix()!r} is not empty — it still holds "
                f"{', '.join(kids[:5])}. Delete what is inside it "
                f"first.")
        target.rmdir()
    else:
        target.unlink()
    return rel.as_posix()
