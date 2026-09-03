"""Bookshelf: a Project's papers — original + normalized text + meta.

Layout (per paper), under the Project's document root (HID §3.6/§3.9):

    Problems/<project>/_docs/<area>/papers/<id>/paper.<ext>
                                              original file
                                              (gitignored: license + size)
    …/<id>/text.md       normalized addressable text (`## p.N` page
                         anchors for PDFs; text sources pass through)
    …/<id>/meta.json     identity + extraction stats
    …/<id>/map.md        navigation index (index.py; absent for
                         small docs / not yet generated)

`<area>` is `user/` or `agent/` — the same two sub-roots the console and
the Assistant write through, chosen here by `meta.added_by`: a person's
upload is the person's document, a fetched one is the engine's. There is
no workspace-global `Papers/` any more (§3.9, 2026-09-03): a paper is a
document OF a Project, reachable in the Documents tab beside everything
else the Project holds, and the same fence that keeps a write inside
`_docs/` keeps a paper there too.

Identity = content hash of the ORIGINAL file bytes (D7): the same paper
added from a different filename/URL lands on the same shelf slot. The
index binds to `text_sha` (hash of text.md), so re-extraction
automatically stales the map (design "索引失效綁抽取").

One paper cited by two Projects is TWO copies under one id (§3.9): a
50MB pdf is not worth a sharing mechanism whose failure mode is a
Project reading a document another Project deleted.

ADDRESSING. A shelf id is still an address on its own — `problem_papers`
stores nothing but the id, and the Context section, the review line and
the console all start from one. So every lookup takes an OPTIONAL
`project`: given, it answers that Project's copy; omitted, it searches
both areas of every Project (papers number in the tens, and a wrong
answer here is a worker reading the wrong Project's document). Nothing
found is `None`, never a made-up path.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from ..state import project_docs as _docs

#: The papers folder's name INSIDE an area. Lower case: it is a folder
#: in a document tree now, not a top-level root.
PAPERS_DIRNAME = "papers"

# Scan detection (QPaper heuristic): a text-bearing PDF averages far
# more than this per page; below it we assume a scanned/image PDF and
# fail loudly — v1 does no OCR, the user supplies a better source.
MIN_CHARS_PER_PAGE = 200

# Small-doc exemption (D9 companion): below this, no index is built —
# the paper is short enough for agents to read whole.
INDEX_MIN_CHARS = 30_000

_TEXT_SUFFIXES = {".md", ".txt", ".tex"}


class ScannedPdfError(RuntimeError):
    """PDF yields too little text — likely scanned. No OCR in v1."""


@dataclass
class PaperMeta:
    id: str
    source_name: str
    pages: int
    chars: int
    text_sha: str
    # Owner-editable display title (UI rename, 2026-07-13): "paper.pdf"
    # names nothing on a shelf. Optional + defaulted so every existing
    # meta.json keeps loading; identity stays the content hash.
    title: "str | None" = None
    # Provenance: 'user' (CLI paper-add / console upload) or 'fetched'
    # (agent download). Optional + defaulted for pre-provenance
    # slots; the first add wins — a re-shelve of the same bytes never
    # rewrites who brought the paper in. It also picks the AREA the
    # paper is shelved in (`area_for`).
    added_by: "str | None" = None


@dataclass(frozen=True)
class ShelfEntry:
    """One paper on one Project's shelf — what a listing needs to name
    it without re-deriving the path three times."""
    project: str
    area: str
    pid: str
    path: Path


def area_for(added_by: "str | None") -> str:
    """Which sub-root a paper belongs in. `user` is the ONE value that
    means a person put it there; everything else (a fetch, a legacy
    slot with no provenance at all) is the engine's."""
    return _docs.AREA_USER if (added_by or "").strip() == _docs.AREA_USER \
        else _docs.AREA_AGENT


def papers_root(workspace: Path, project: str,
                area: str = _docs.AREA_AGENT) -> Path:
    """`Problems/<project>/_docs/<area>/papers`.

    The Project name is validated by `project_docs.root` — it is a path
    component, and this is the one place the papers tree is spelled."""
    if area not in _docs.AREAS:
        raise ValueError(f"unknown docs area {area!r}; "
                         f"expected one of {' '.join(_docs.AREAS)}")
    return _docs.root(workspace, project) / area / PAPERS_DIRNAME


def _projects_on_disk(workspace: Path) -> "list[str]":
    """Every Project directory that has a document root, name order.

    The filesystem, not the DB: this module is imported by offline
    callers (the CLI, a fresh workspace, the migration's dry run) that
    have no connection, and a shelf lookup must not need one."""
    base = Path(workspace) / "Problems"
    try:
        return sorted(p.name for p in base.iterdir()
                      if (p / _docs.ROOT_DIRNAME).is_dir())
    except OSError:
        return []


def list_papers(workspace: Path, *,
                project: "str | None" = None) -> "list[ShelfEntry]":
    """Every shelved paper, or one Project's. A directory without a
    `meta.json` is not a shelf slot and is skipped — the tree is a
    document tree, and a person may put any folder in it."""
    out: "list[ShelfEntry]" = []
    names = [project] if project else _projects_on_disk(workspace)
    for name in names:
        for area in _docs.AREAS:
            try:
                root = papers_root(workspace, name, area)
            except ValueError:
                continue  # not a legal Project name — not a shelf
            if not root.is_dir():
                continue
            for pdir in sorted(root.iterdir()):
                if (pdir / "meta.json").is_file():
                    out.append(ShelfEntry(project=name, area=area,
                                          pid=pdir.name, path=pdir))
    return out


def paper_dir(workspace: Path, pid: str, *,
              project: "str | None" = None) -> "Path | None":
    """Where paper `pid` is shelved, or None.

    With `project`, that Project's copy (both areas are searched — the
    area is a property of the slot, not of the caller). Without one,
    every Project's, in name order: the id is the address the DB keeps,
    and a caller that only has an id still has to be able to open it."""
    if not pid or "/" in pid or "\\" in pid or pid in (".", ".."):
        return None
    for entry in list_papers(workspace, project=project):
        if entry.pid == pid:
            return entry.path
    return None


def text_path(workspace: Path, pid: str, *,
              project: "str | None" = None) -> "Path | None":
    d = paper_dir(workspace, pid, project=project)
    return None if d is None else d / "text.md"


def map_path(workspace: Path, pid: str, *,
             project: "str | None" = None) -> "Path | None":
    d = paper_dir(workspace, pid, project=project)
    return None if d is None else d / "map.md"


def _sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def content_id(data: bytes) -> str:
    """Shelf identity for a would-be paper's raw bytes (D7) — lets a
    caller ask "is this already shelved?" without duplicating the
    hash rule."""
    return _sha12(data)


def load_meta(workspace: Path, pid: str, *,
              project: "str | None" = None) -> "PaperMeta | None":
    d = paper_dir(workspace, pid, project=project)
    if d is None:
        return None
    try:
        return PaperMeta(**json.loads(
            (d / "meta.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def set_title(workspace: Path, pid: str, title: "str | None", *,
              project: "str | None" = None) -> "PaperMeta | None":
    """Rename a paper's DISPLAY title (empty/whitespace clears it back
    to the filename). Display metadata only — id, text and bindings are
    untouched."""
    d = paper_dir(workspace, pid, project=project)
    meta = load_meta(workspace, pid, project=project)
    if meta is None or d is None:
        return None
    meta.title = (title or "").strip() or None
    (d / "meta.json").write_text(
        json.dumps(asdict(meta), indent=2), encoding="utf-8")
    return meta


def _extract_pdf(src: Path) -> "tuple[str, int]":
    """PDF → page-anchored markdown. Raises ScannedPdfError on a
    text-starved document (fail loud; original PDF stays readable as
    the agent-side fallback either way)."""
    import fitz  # PyMuPDF — lazy: text-source adds don't need it

    parts: "list[str]" = []
    total = 0
    with fitz.open(str(src)) as doc:
        n_pages = doc.page_count
        for i in range(n_pages):
            # PyMuPDF can emit NUL bytes (font quirks); a single one
            # makes ripgrep/Grep classify text.md as binary and refuse
            # to match — agents lose their main navigation tool
            # (observed live, first paper-bound run 2026-07-06).
            text = doc[i].get_text("text").replace("\x00", "").strip()
            total += len(text)
            parts.append(f"## p.{i + 1}\n\n{text}\n")
    if n_pages and total / n_pages < MIN_CHARS_PER_PAGE:
        raise ScannedPdfError(
            f"{src.name}: {total} chars over {n_pages} pages "
            f"(< {MIN_CHARS_PER_PAGE}/page) — likely a scanned PDF. "
            f"v1 does no OCR; supply a text-bearing source "
            f"(arXiv LaTeX/PDF preferred).")
    return "\n".join(parts), n_pages


def add_paper(workspace: Path, src: Path, *,
              project: str,
              force: bool = False,
              added_by: "str | None" = None) -> PaperMeta:
    """Shelve `src` on `project`'s shelf (idempotent by content hash).
    PDF → extracted page-anchored text; .md/.txt/.tex → passthrough.
    `force` re-runs extraction over an existing slot (extractor
    improved); the map's text_sha binding then flags itself stale.
    `added_by` records provenance ('user' / 'fetched') on a NEW slot and
    picks its area; an existing slot keeps both — a re-shelve never
    moves a paper between the two owners' areas."""
    data = src.read_bytes()
    pid = _sha12(data)
    existing = load_meta(workspace, pid, project=project)
    if existing is not None and not force:
        print(f"[papers] {src.name} already shelved as {pid} "
              f"(content-hash match)", flush=True)
        return existing
    here = paper_dir(workspace, pid, project=project)
    pdir = here if here is not None else (
        papers_root(workspace, project, area_for(added_by)) / pid)

    suffix = src.suffix.lower()
    if suffix == ".pdf":
        text, pages = _extract_pdf(src)
    elif suffix in _TEXT_SUFFIXES:
        text = data.decode("utf-8", errors="replace")
        pages = 0  # not paged; addressable by its own structure
    else:
        raise ValueError(
            f"unsupported paper format {suffix!r} "
            f"(accepted: .pdf, {', '.join(sorted(_TEXT_SUFFIXES))})")

    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"paper{suffix}").write_bytes(data)
    (pdir / "text.md").write_text(text, encoding="utf-8")
    # A `force` re-extraction rebuilds meta.json — it must carry the
    # display/provenance fields of the slot it overwrites, or a
    # re-extract silently wipes the owner's rename.
    meta = PaperMeta(
        id=pid, source_name=src.name, pages=pages, chars=len(text),
        text_sha=_sha12(text.encode("utf-8")),
        title=existing.title if existing else None,
        added_by=(existing.added_by if existing else None) or added_by)
    (pdir / "meta.json").write_text(
        json.dumps(asdict(meta), indent=2), encoding="utf-8")
    print(f"[papers] shelved {src.name} → "
          f"{pdir.relative_to(workspace).as_posix()} "
          f"({pages or 'unpaged'} pages, {len(text)} chars)", flush=True)
    return meta


def copy_into_project(workspace: Path, pid: str,
                      project: str) -> "Path | None":
    """Make sure `project` holds its own copy of paper `pid`; returns
    where it is, or None when the id is on no shelf at all.

    A COPY, never a move (§3.9): the Project it came from may still have
    problems citing it, and moving the file out from under them would
    blind a worker mid-run. Idempotent — a Project that already holds
    the id keeps the copy it has, extraction and title included."""
    have = paper_dir(workspace, pid, project=project)
    if have is not None:
        return have
    src = paper_dir(workspace, pid)
    if src is None:
        return None
    meta = load_meta(workspace, pid)
    dst = papers_root(workspace, project,
                      area_for(meta.added_by if meta else None)) / pid
    dst.parent.mkdir(parents=True, exist_ok=True)
    # `.index_attempt/` is the map spawn's sandbox, not part of the
    # paper — a copy carries the document, not the last agent's scratch.
    shutil.copytree(src, dst,
                    ignore=shutil.ignore_patterns(".index_attempt"))
    return dst


# ── map staleness (index ↔ extraction binding) ──

_MAP_SHA_KEY = "text_sha:"


def map_text_sha(workspace: Path, pid: str, *,
                 project: "str | None" = None) -> "str | None":
    """`text_sha` recorded in map.md's frontmatter (framework-stamped
    by index.generate_index), or None when no/unstamped map."""
    p = map_path(workspace, pid, project=project)
    if p is None:
        return None
    try:
        head = p.read_text(encoding="utf-8")[:400]
    except OSError:
        return None
    for line in head.splitlines():
        if line.strip().startswith(_MAP_SHA_KEY):
            return line.split(_MAP_SHA_KEY, 1)[1].strip()
    return None


def map_is_stale(workspace: Path, pid: str, *,
                 project: "str | None" = None) -> bool:
    """True iff a map exists but was built against different text
    (re-extraction happened). Absent map is not 'stale' — it's absent."""
    recorded = map_text_sha(workspace, pid, project=project)
    if recorded is None:
        return False
    meta = load_meta(workspace, pid, project=project)
    return meta is None or recorded != meta.text_sha
