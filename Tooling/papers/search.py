"""`python -m Tooling.papers.search '<query>'` — the Scholar agent's
citation-resolution command (paper v2, D12).

One curated network surface: aggregates OpenAlex (fuzzy citation →
DOI + OA locations), Crossref (bibliographic → DOI), and arXiv
(preprint search). Prints a compact JSON list; the agent judges which
hit is the cited work and whether any location is fetchable
(`papers.fetch` accepts only whitelisted hosts — see fetch.py).

Source matrix (2026-07-07 live probe, design doc): the metadata layer
is fully open (no keys); Semantic Scholar 429s without a key and is
deliberately absent (OpenAlex covers it).
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

_MAILTO = "asterism@example.org"  # polite-pool identification
_TIMEOUT = 20
_PER_SOURCE = 3


def _get_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": f"AsterismScholar/0.1 "
                                        f"(mailto:{_MAILTO})"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001 — one source down ≠ no answer
        print(f"[search] WARN {url.split('?')[0]}: {e}", file=sys.stderr)
        return None


def _get_text(url: str) -> str:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": f"AsterismScholar/0.1 "
                                        f"(mailto:{_MAILTO})"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        print(f"[search] WARN {url.split('?')[0]}: {e}", file=sys.stderr)
        return ""


def _openalex(query: str) -> list[dict]:
    q = urllib.parse.quote(query)
    d = _get_json(f"https://api.openalex.org/works?search={q}"
                  f"&per_page={_PER_SOURCE}&mailto={_MAILTO}")
    out = []
    for w in (d or {}).get("results", []):
        loc = w.get("best_oa_location") or {}
        out.append({
            "source": "openalex",
            "title": w.get("title"),
            "year": w.get("publication_year"),
            "doi": w.get("doi"),
            "oa_status": (w.get("open_access") or {}).get("oa_status"),
            "pdf_url": loc.get("pdf_url"),
            "landing_url": loc.get("landing_page_url"),
        })
    return out


def _crossref(query: str) -> list[dict]:
    q = urllib.parse.quote(query)
    d = _get_json(f"https://api.crossref.org/works?query.bibliographic={q}"
                  f"&rows={_PER_SOURCE}&mailto={_MAILTO}")
    out = []
    for it in ((d or {}).get("message") or {}).get("items", []):
        out.append({
            "source": "crossref",
            "title": (it.get("title") or [None])[0],
            "year": ((it.get("issued") or {}).get("date-parts")
                     or [[None]])[0][0],
            "doi": it.get("DOI"),
        })
    return out


def _arxiv(query: str) -> list[dict]:
    q = urllib.parse.quote(f'all:"{query}"' if " " in query else query)
    xml = _get_text(f"https://export.arxiv.org/api/query?"
                    f"search_query={q}&max_results={_PER_SOURCE}")
    out = []
    import re
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        def _tag(t: str) -> str:
            m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", entry, re.DOTALL)
            return (m.group(1).strip() if m else "")
        arxiv_id = _tag("id").rsplit("/abs/", 1)[-1]
        out.append({
            "source": "arxiv",
            "title": " ".join(_tag("title").split()),
            "year": _tag("published")[:4],
            "arxiv_id": arxiv_id,
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}"
                       if arxiv_id else None,
        })
    return out


def _unpaywall(doi: str) -> list[dict]:
    doi = doi.removeprefix("https://doi.org/")
    d = _get_json(f"https://api.unpaywall.org/v2/"
                  f"{urllib.parse.quote(doi)}?email={_MAILTO}")
    out = []
    for loc in (d or {}).get("oa_locations", [])[:4]:
        out.append({
            "source": "unpaywall",
            "host_type": loc.get("host_type"),
            "pdf_url": loc.get("url_for_pdf") or loc.get("url"),
        })
    return out


def _enrich_via_unpaywall(hits: list[dict], cap: int = 3) -> None:
    """Attach a pdf_url to DOI-only hits, in place.

    The search side used to hand back rows with a DOI and no pdf_url,
    while _unpaywall — one lookup away, in this same module — knew the
    direct open-access PDF (Erdos.p1, 2026-08-22: the exact 1996 target
    came back DOI-only from Crossref while unpaywall held its ams.org
    PDF; the scholar was left to fetch doi.org and be refused). The
    framework held both halves of the answer — join them here, once,
    rather than teach every caller a second round-trip. `cap` bounds
    the extra lookups per search."""
    for hit in hits:
        if cap <= 0:
            return
        if hit.get("pdf_url") or not hit.get("doi"):
            continue
        cap -= 1
        for loc in _unpaywall(str(hit["doi"])):
            if loc.get("pdf_url"):
                hit["pdf_url"] = loc["pdf_url"]
                hit["pdf_via"] = "unpaywall"
                break


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m Tooling.papers.search '<citation/query>'"
              "  |  --doi <doi> (list OA copies)")
        return 2
    if args[0] == "--doi" and len(args) > 1:
        hits = _unpaywall(args[1])
    else:
        query = " ".join(args)
        hits = _openalex(query) + _arxiv(query) + _crossref(query)
        _enrich_via_unpaywall(hits)
    print(json.dumps(hits, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
