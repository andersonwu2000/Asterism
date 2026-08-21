"""`python -m Tooling.papers.fetch <url|arxiv_id> --problem <p>` — the
Scholar agent's download command (paper v2, D12/D15).

The ONLY network surface that writes to disk. Whitelisted hosts only
(arXiv-class; publisher sites serve cookie/JS interstitials even for
OA content — 2026-07-07 probe — and are deliberately refused: that is
the human-request path, not an arms race to fight). On success the
file is shelved (`shelf.add_paper` — content-hash dedupe), indexed
when large enough, and bound to `--problem` with origin='scholar'.

Caps (D15): per-problem scholar fetches, single-file size.
"""
from __future__ import annotations

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
    shelf id. Raises ValueError/RuntimeError loudly on refusal."""
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
    conn = db.connect(workspace / "asterism.db") \
        if (workspace / "asterism.db").exists() else None
    try:
        if problem and conn is not None:
            n = db.scholar_fetch_count(conn, problem)
            if n >= MAX_SCHOLAR_FETCHES_PER_PROBLEM:
                raise RuntimeError(
                    f"per-problem scholar fetch cap reached "
                    f"({n}/{MAX_SCHOLAR_FETCHES_PER_PROBLEM}) — justify "
                    f"further papers to the human instead")

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
        tmp = workspace / "Papers" / ".dl" / name
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        try:
            meta = shelf.add_paper(workspace, tmp, added_by="fetched")
        finally:
            try:
                tmp.unlink()
                tmp.parent.rmdir()
            except OSError:
                pass
        print(f"[fetch] shelved {url} → Papers/{meta.id}", flush=True)
        if meta.chars >= shelf.INDEX_MIN_CHARS \
                and not shelf.map_path(workspace, meta.id).exists():
            from ..pipeline import PROMPT_DIR
            paper_index.generate_index(workspace, meta.id,
                                       prompt_dir=PROMPT_DIR)
        if problem and conn is not None:
            db.bind_paper(conn, problem=problem, paper_id=meta.id,
                          origin="scholar", reason=reason or url)
            print(f"[fetch] bound Papers/{meta.id} → {problem}",
                  flush=True)
        return meta.id
    finally:
        if conn is not None:
            conn.close()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="Tooling.papers.fetch")
    ap.add_argument("target", help="whitelisted URL or arXiv id")
    ap.add_argument("--problem", default=None,
                    help="bind the fetched paper to this problem")
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
