"""`python -m Tooling.papers.fetch <url|arxiv_id> --problem <p>` — the
Scholar agent's download command (paper v2, D12/D15).

The ONLY network surface that writes to disk. Whitelisted hosts only
(arXiv-class; publisher sites serve cookie/JS interstitials even for
OA content — 2026-07-07 probe — and are deliberately refused: that is
the human-request path, not an arms race to fight). On success the
file is shelved (`shelf.add_paper` — content-hash dedupe), indexed
when large enough, and bound to `--problem` with the calling seat as origin.

Caps (D15): per-problem scholar fetches, single-file size.
"""
from __future__ import annotations

import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

FETCH_HOST_WHITELIST = frozenset({
    "arxiv.org", "export.arxiv.org",
    # Publisher-run open archives (2026-08-05, user call): the classical
    # 3-manifold literature largely predates arXiv (Hass 1987 died
    # paper_unfetchable with the AMS PDF as its only open copy), and the
    # non-PDF-response refusal already rejects any paywall page loudly.
    "www.ams.org", "ams.org",
    "projecteuclid.org", "www.projecteuclid.org",
    "msp.org", "www.msp.org",
    # Cambridge Core (2026-08-22, user call): CMS journal backfiles are
    # free there — Moser's CMB 1963 paper died paper_unfetchable with
    # the Cambridge PDF as its only open copy (same shape as Hass).
    "www.cambridge.org", "cambridge.org",
})

# doi.org is a REDIRECTOR, not a host — refusing it with the generic
# whitelist message taught nothing reachable (Erdos.p1, 2026-08-22: the
# scholar held a DOI whose open copy sat on whitelisted ams.org, one
# paper_search(doi=…) away). The gate must name that move.
_DOI_REDIRECTOR_HOSTS = frozenset({"doi.org", "www.doi.org", "dx.doi.org"})
MAX_FETCH_BYTES = 50 * 1024 * 1024
# 5 → 20 (2026-08-05, user call): a research-grade survey legitimately
# needs 7+ papers (SLC restart hit 6 in its first two batches and the
# cap would have killed the LAST in-flight bind — possibly Louder, the
# highest-value fetch). Papers on the shelf are lazy-loaded assets —
# readers pay only for what they open — and every fetch now rides the
# judged math turn, so the mechanical cap is a runaway backstop, not
# the budget.
MAX_SCHOLAR_FETCHES_PER_PROBLEM = 20

# New-style (2007+) `2605.23679` and old-style `math/0601146` /
# `math.GT/0601146` arXiv ids both resolve to arxiv.org/pdf/<id>.
_ARXIV_ID_RE = re.compile(
    r"^(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})(v\d+)?$")


def _resolve_url(target: str) -> str:
    if _ARXIV_ID_RE.match(target):
        return f"https://arxiv.org/pdf/{target}"
    return target


def fetch_and_shelve(workspace: Path, target: str, *,
                     problem: str | None, reason: str | None) -> str:
    """Download → shelve → index (size-gated) → bind. Returns the
    shelf id. Raises ValueError/RuntimeError loudly on refusal.

    `problem` is REQUIRED now (§3.9): a paper is a document of the
    Project the problem sits on, and with no workspace-global shelf
    left there is no third place to put one. The refusal says so."""
    url = _resolve_url(target)
    host = urllib.parse.urlparse(url).hostname or ""
    if host in _DOI_REDIRECTOR_HOSTS:
        doi = urllib.parse.urlparse(url).path.lstrip("/")
        raise ValueError(
            f"{host} is a DOI redirector, not a paper host — its landing "
            f"page is rarely the PDF. Resolve the open copies first: "
            f'paper_search(doi="{doi}") lists direct pdf_url locations; '
            f"fetch one of those instead.")
    if host not in FETCH_HOST_WHITELIST:
        raise ValueError(
            f"host {host!r} is not fetch-whitelisted "
            f"({sorted(FETCH_HOST_WHITELIST)}). If the paper only "
            f"exists there, report the exact URL/DOI back — the "
            f"framework asks the human instead.")

    from ..state import db
    from ..state import projects as _projects
    if not (problem or "").strip():
        raise ValueError(
            "a fetched paper is shelved on a Project's document shelf, "
            "so this needs the problem it is for: pass `problem` (e.g. "
            "paper_fetch(target=..., problem=\"Erdos.p1\", reason=...)).")
    conn = db.connect(workspace / "asterism.db") \
        if (workspace / "asterism.db").exists() else None
    try:
        project = None
        if conn is not None:
            n = db.scholar_fetch_count(conn, problem)
            if n >= MAX_SCHOLAR_FETCHES_PER_PROBLEM:
                raise RuntimeError(
                    f"per-problem paper fetch cap reached "
                    f"({n}/{MAX_SCHOLAR_FETCHES_PER_PROBLEM}) — justify "
                    f"further papers to the human instead")
            project = _projects.project_of(conn, problem)
        # The Project is the shelf (§3.9). With no DB — an offline
        # workspace — the problem name's first segment is the same
        # default registration would have picked (§3.1).
        project = project or problem.split(".", 1)[0]

        req = urllib.request.Request(
            url, headers={"User-Agent": "AsterismScholar/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(MAX_FETCH_BYTES + 1)
        if len(data) > MAX_FETCH_BYTES:
            raise RuntimeError(f"download exceeds {MAX_FETCH_BYTES}B cap")
        if not data.startswith(b"%PDF"):
            raise RuntimeError(
                "response is not a PDF (interstitial/HTML?) — do not "
                "retry the same URL; report it for the human path")

        from . import shelf, index as paper_index
        # The download's basename becomes the shelf `source_name`
        # (shown in the Context auxiliary line) — derive a meaningful
        # one instead of a temp-file name (live blemish 2026-07-07:
        # RHD07 displayed as `_fetch_tmp.pdf`).
        if _ARXIV_ID_RE.match(target):
            name = "arxiv_" + target.replace("/", "_") + ".pdf"
        else:
            name = (urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
                    or "paper")
            if not name.endswith(".pdf"):
                name += ".pdf"
        # The staging file is the OS's temp dir, not a corner of the
        # workspace: the download is not a document until it is shelved,
        # and a half-written one under `Problems/` is a folder the
        # console would draw (`Papers/.dl/` was that corner).
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / name
            tmp.write_bytes(data)
            meta = shelf.add_paper(workspace, tmp, project=project,
                                   added_by="fetched")
        rel = shelf.paper_dir(workspace, meta.id, project=project)
        print(f"[fetch] shelved {url} → "
              f"{rel.relative_to(workspace).as_posix()}", flush=True)
        mpath = shelf.map_path(workspace, meta.id, project=project)
        if meta.chars >= shelf.INDEX_MIN_CHARS \
                and (mpath is None or not mpath.exists()):
            from ..pipeline import PROMPT_DIR
            paper_index.generate_index(workspace, meta.id,
                                       prompt_dir=PROMPT_DIR,
                                       project=project, problem=problem)
        if conn is not None:
            # Provenance = the calling seat (ASTERISM_SEAT travels in the
            # MCP server env; the shim's in-process path has none and
            # lands on 'agent'). 'scholar' used to be hardcoded here and
            # mislabelled a strategist's direct fetch (2026-08-22).
            db.bind_paper(conn, problem=problem, paper_id=meta.id,
                          origin=os.environ.get("ASTERISM_SEAT") or "agent",
                          reason=reason or url)
            print(f"[fetch] bound {meta.id} → {problem}", flush=True)
        return meta.id
    finally:
        if conn is not None:
            conn.close()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="Tooling.papers.fetch")
    ap.add_argument("target", help="whitelisted URL or arXiv id")
    ap.add_argument("--problem", default=None,
                    help="the problem this paper is for — it names the "
                         "Project whose document shelf holds it, and the "
                         "binding is made there (required)")
    ap.add_argument("--reason", default=None,
                    help="why this paper is needed (binding audit)")
    ap.add_argument("--workspace", default=".",
                    help="workspace root (defaults to cwd)")
    a = ap.parse_args(argv)
    try:
        pid = fetch_and_shelve(Path(a.workspace).resolve(), a.target,
                               problem=a.problem, reason=a.reason)
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}")
        return 1
    print(f"OK: {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
