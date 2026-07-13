"""Bookshelf: `Papers/<id>/` — original + normalized text + meta.

Layout (per paper):
    Papers/<id>/paper.<ext>   original file (gitignored: license + size)
    Papers/<id>/text.md       normalized addressable text (`## p.N` page
                              anchors for PDFs; text sources pass through)
    Papers/<id>/meta.json     identity + extraction stats
    Papers/<id>/map.md        navigation index (index.py; absent for
                              small docs / not yet generated)

Identity = content hash of the ORIGINAL file bytes (D7): the same paper
added from a different filename/URL lands on the same shelf slot. The
index binds to `text_sha` (hash of text.md), so re-extraction
automatically stales the map (design "索引失效綁抽取").
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

PAPERS_DIRNAME = "Papers"

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


def set_title(workspace: Path, pid: str, title: "str | None") -> "PaperMeta | None":
    """Rename a paper's DISPLAY title (empty/whitespace clears it back
    to the filename). Display metadata only — id, text and bindings are
    untouched."""
    meta = load_meta(workspace, pid)
    if meta is None:
        return None
    meta.title = (title or "").strip() or None
    (paper_dir(workspace, pid) / "meta.json").write_text(
        json.dumps(asdict(meta), indent=2), encoding="utf-8")
    return meta


def papers_root(workspace: Path) -> Path:
    return workspace / PAPERS_DIRNAME


def paper_dir(workspace: Path, pid: str) -> Path:
    return papers_root(workspace) / pid


def text_path(workspace: Path, pid: str) -> Path:
    return paper_dir(workspace, pid) / "text.md"


def map_path(workspace: Path, pid: str) -> Path:
    return paper_dir(workspace, pid) / "map.md"


def _sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def load_meta(workspace: Path, pid: str) -> PaperMeta | None:
    p = paper_dir(workspace, pid) / "meta.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return PaperMeta(**d)
    except (OSError, ValueError, TypeError):
        return None


def _extract_pdf(src: Path) -> tuple[str, int]:
    """PDF → page-anchored markdown. Raises ScannedPdfError on a
    text-starved document (fail loud; original PDF stays readable as
    the agent-side fallback either way)."""
    import fitz  # PyMuPDF — lazy: text-source adds don't need it

    parts: list[str] = []
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
              force: bool = False) -> PaperMeta:
    """Add `src` to the shelf (idempotent by content hash). PDF →
    extracted page-anchored text; .md/.txt/.tex → passthrough.
    `force` re-runs extraction over an existing slot (extractor
    improved); the map's text_sha binding then flags itself stale."""
    data = src.read_bytes()
    pid = _sha12(data)
    pdir = paper_dir(workspace, pid)
    existing = load_meta(workspace, pid)
    if existing is not None and not force:
        print(f"[papers] {src.name} already shelved as {pid} "
              f"(content-hash match)", flush=True)
        return existing

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
    text_path(workspace, pid).write_text(text, encoding="utf-8")
    meta = PaperMeta(
        id=pid, source_name=src.name, pages=pages, chars=len(text),
        text_sha=_sha12(text.encode("utf-8")))
    (pdir / "meta.json").write_text(
        json.dumps(asdict(meta), indent=2), encoding="utf-8")
    print(f"[papers] shelved {src.name} → Papers/{pid} "
          f"({pages or 'unpaged'} pages, {len(text)} chars)", flush=True)
    return meta


# ── map staleness (index ↔ extraction binding) ──

_MAP_SHA_KEY = "text_sha:"


def map_text_sha(workspace: Path, pid: str) -> str | None:
    """`text_sha` recorded in map.md's frontmatter (framework-stamped
    by index.generate_index), or None when no/unstamped map."""
    p = map_path(workspace, pid)
    try:
        head = p.read_text(encoding="utf-8")[:400]
    except OSError:
        return None
    for line in head.splitlines():
        if line.strip().startswith(_MAP_SHA_KEY):
            return line.split(_MAP_SHA_KEY, 1)[1].strip()
    return None


def map_is_stale(workspace: Path, pid: str) -> bool:
    """True iff a map exists but was built against different text
    (re-extraction happened). Absent map is not 'stale' — it's absent."""
    recorded = map_text_sha(workspace, pid)
    if recorded is None:
        return False
    meta = load_meta(workspace, pid)
    return meta is None or recorded != meta.text_sha
