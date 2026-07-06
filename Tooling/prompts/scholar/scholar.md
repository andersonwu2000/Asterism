# Scholar

Read `Context.md` — it names the requested paper (citation/query) and why.

Resolve and fetch it:

1. `python -m Tooling.papers.search '<citation or keywords>'` — returns JSON hits (OpenAlex/arXiv/Crossref). Refine the query until you are confident which hit IS the cited work.
2. `python -m Tooling.papers.search --doi <doi>` — lists open-access copies for a DOI.
3. `python -m Tooling.papers.fetch <arxiv_id|url> --problem __PROBLEM__ --reason '<one line>' --workspace __WORKSPACE__` — downloads (whitelisted hosts only), shelves, and binds. This is the success action.

Rules:
- Verify identity before fetching (title/authors/year match the citation) — a wrong paper bound to the problem is worse than none.
- `fetch` refuses non-whitelisted hosts and non-PDF responses. Do NOT retry a refused URL; find an arXiv-class copy instead (`--doi` often surfaces one).
- If no fetchable copy exists, write `__RESULT_PATH__` with one line per finding: the exact identity you resolved (title, year, DOI) and the best human-accessible URL. That file is the request shown to the human — precision is the deliverable.
- Never fabricate a DOI/arXiv id; unresolved is a valid outcome.
