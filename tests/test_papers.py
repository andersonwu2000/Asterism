"""Paper pipeline Phase 1 (docs/internal/archive/paper_pipeline_design.md):
shelf identity/extraction, index staleness binding, small-doc
exemption, DB paper bindings, Context paper-index section."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import agent as agent_pkg
from Tooling.papers import index as paper_index
from Tooling.papers import shelf
from Tooling.state import intent

# Absolute, cwd-independent — `Path("Tooling/prompts").resolve()` broke the
# suite when pytest ran from any cwd other than the repo root (production
# callers use the module-relative pipeline.PROMPT_DIR, which is absolute).
_PROMPT_DIR = Path(__file__).resolve().parents[1] / "Tooling" / "prompts"


# ---------------------------------------------------------------------
# shelf
# ---------------------------------------------------------------------

#: Every shelved paper now lives under a Project's document root
#: (HID §3.9) — there is no workspace-global `Papers/` any more, so
#: every add names the Project it is shelved for.
_PROJECT = "Test"


def _add_text_paper(ws: Path, body: str, name: str = "notes.md",
                    project: str = _PROJECT, added_by: "str | None" = None):
    src = ws / name
    src.write_text(body, encoding="utf-8")
    return shelf.add_paper(ws, src, project=project, added_by=added_by)


def test_papers_root_is_under_the_project_docs_root(tmp_path: Path) -> None:
    """§3.9: the shelf retires into `Problems/<project>/_docs/<area>/
    papers/`. `<area>` is the write fence §3.6 already owns — the paper
    root is a folder inside it, not a fourth root beside it."""
    from Tooling.state import project_docs as pd
    root = shelf.papers_root(tmp_path, "Erdos", pd.AREA_AGENT)
    assert root == (pd.root(tmp_path, "Erdos") / pd.AREA_AGENT / "papers")
    # and the workspace-global shelf is gone
    assert not hasattr(shelf, "PAPERS_DIRNAME") or \
        shelf.PAPERS_DIRNAME != "Papers"


def test_add_paper_area_follows_added_by(tmp_path: Path) -> None:
    """`meta.added_by` decides the area (§3.9): a person's upload lands
    in `user/`, everything the engine fetched in `agent/`. The two are
    different owners, which is what the area split means."""
    from Tooling.state import project_docs as pd
    mine = _add_text_paper(tmp_path, "human\n", name="h.md",
                           added_by="user")
    theirs = _add_text_paper(tmp_path, "engine\n", name="e.md",
                             added_by="fetched")
    assert shelf.paper_dir(tmp_path, mine.id).parent == \
        shelf.papers_root(tmp_path, _PROJECT, pd.AREA_USER)
    assert shelf.paper_dir(tmp_path, theirs.id).parent == \
        shelf.papers_root(tmp_path, _PROJECT, pd.AREA_AGENT)


def test_paper_dir_resolves_a_bare_pid_across_projects(
        tmp_path: Path) -> None:
    """A shelf id is still an address on its own: `paper_dir` searches
    both areas of every Project when no Project is known (papers are
    few), and answers None for an id nothing shelved."""
    a = _add_text_paper(tmp_path, "one\n", name="a.md", project="Erdos")
    b = _add_text_paper(tmp_path, "two\n", name="b.md", project="Topology",
                        added_by="user")
    assert shelf.paper_dir(tmp_path, a.id).parts[-5:-2] == \
        ("Erdos", "_docs", "agent")
    assert shelf.paper_dir(tmp_path, b.id).parts[-5:-2] == \
        ("Topology", "_docs", "user")
    assert shelf.load_meta(tmp_path, a.id).source_name == "a.md"
    assert shelf.paper_dir(tmp_path, "deadbeef0000") is None
    assert shelf.load_meta(tmp_path, "deadbeef0000") is None


def test_paper_dir_prefers_the_named_project(tmp_path: Path) -> None:
    """Same bytes shelved under two Projects = two copies with the same
    id (§3.9: 50MB is not worth a sharing mechanism). Asking with a
    Project must answer that Project's copy."""
    src = tmp_path / "same.md"
    src.write_text("shared body\n", encoding="utf-8")
    one = shelf.add_paper(tmp_path, src, project="Erdos")
    two = shelf.add_paper(tmp_path, src, project="Topology")
    assert one.id == two.id
    assert shelf.paper_dir(tmp_path, one.id, project="Erdos") != \
        shelf.paper_dir(tmp_path, one.id, project="Topology")
    assert shelf.paper_dir(tmp_path, one.id, project="Erdos").is_dir()
    assert shelf.paper_dir(tmp_path, one.id, project="Topology").is_dir()


def test_copy_into_project_is_a_copy_not_a_move(tmp_path: Path) -> None:
    """Binding a paper to a problem on another shelf copies it there
    (§3.9) — the Project it came from keeps its own copy, because a
    move would blind the problems still citing it."""
    meta = _add_text_paper(tmp_path, "body\n", project="Erdos")
    src_dir = shelf.paper_dir(tmp_path, meta.id, project="Erdos")
    dst = shelf.copy_into_project(tmp_path, meta.id, "Topology")
    assert dst is not None and dst.is_dir()
    assert src_dir.is_dir()
    assert (dst / "text.md").read_text(encoding="utf-8") == \
        (src_dir / "text.md").read_text(encoding="utf-8")
    # idempotent: a second call is the same directory, not a duplicate
    assert shelf.copy_into_project(tmp_path, meta.id, "Topology") == dst


def test_list_papers_reports_project_and_area(tmp_path: Path) -> None:
    """The shelf listing the console and the migration both read."""
    a = _add_text_paper(tmp_path, "one\n", name="a.md", project="Erdos",
                        added_by="user")
    b = _add_text_paper(tmp_path, "two\n", name="b.md", project="Topology")
    rows = {r.pid: r for r in shelf.list_papers(tmp_path)}
    assert rows[a.id].project == "Erdos" and rows[a.id].area == "user"
    assert rows[b.id].project == "Topology" and rows[b.id].area == "agent"
    only = shelf.list_papers(tmp_path, project="Erdos")
    assert [r.pid for r in only] == [a.id]


def test_add_text_paper_identity_and_idempotence(tmp_path: Path) -> None:
    meta = _add_text_paper(tmp_path, "# Theorem 1\n\nAll is well.\n")
    pdir = shelf.paper_dir(tmp_path, meta.id)
    assert (pdir / "paper.md").is_file()
    assert shelf.text_path(tmp_path, meta.id).is_file()
    assert meta.pages == 0  # text source: unpaged
    # Same bytes under a different name → same shelf slot (D7).
    again = _add_text_paper(tmp_path, "# Theorem 1\n\nAll is well.\n",
                            name="renamed.md")
    assert again.id == meta.id


def test_add_paper_provenance_first_add_wins(tmp_path: Path) -> None:
    """`added_by` records who brought the paper in; a later re-shelve
    of the same bytes (any caller) never rewrites it."""
    src = tmp_path / "notes.md"
    src.write_text("body\n", encoding="utf-8")
    meta = shelf.add_paper(tmp_path, src, project=_PROJECT,
                           added_by="fetched")
    assert meta.added_by == "fetched"
    again = shelf.add_paper(tmp_path, src, project=_PROJECT,
                            added_by="user")
    assert again.added_by == "fetched"
    # persisted, not just returned
    assert shelf.load_meta(tmp_path, meta.id).added_by == "fetched"


def test_force_reextract_keeps_title_and_provenance(tmp_path: Path) -> None:
    """`--force` rebuilds meta.json from a fresh extraction — it must
    carry the slot's display/provenance fields, or a re-extract wipes
    the owner's rename (live class of bug: force path built PaperMeta
    from scratch)."""
    src = tmp_path / "notes.md"
    src.write_text("body\n", encoding="utf-8")
    meta = shelf.add_paper(tmp_path, src, project=_PROJECT,
                           added_by="user")
    shelf.set_title(tmp_path, meta.id, "Residues, applied")
    meta2 = shelf.add_paper(tmp_path, src, project=_PROJECT, force=True)
    assert meta2.title == "Residues, applied"
    assert meta2.added_by == "user"


def test_add_paper_rejects_unknown_format(tmp_path: Path) -> None:
    src = tmp_path / "paper.docx"
    src.write_bytes(b"not a pdf")
    with pytest.raises(ValueError, match="unsupported paper format"):
        shelf.add_paper(tmp_path, src, project=_PROJECT)


def test_pdf_extraction_page_anchors(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    src = tmp_path / "two_pages.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        for row in range(20):
            page.insert_text((72, 72 + 14 * row),
                             f"Page {i + 1} body line {row}. " * 3)
    doc.save(str(src))
    doc.close()
    meta = shelf.add_paper(tmp_path, src, project=_PROJECT)
    text = shelf.text_path(tmp_path, meta.id).read_text(encoding="utf-8")
    assert meta.pages == 2
    assert "## p.1" in text and "## p.2" in text
    assert "Page 2 body line 0." in text


def test_pdf_extraction_strips_nul_bytes(tmp_path: Path) -> None:
    """PyMuPDF can emit NULs; one NUL makes Grep classify text.md as
    binary and refuse to match (live, first paper-bound run). The
    extractor strips them; `--force` re-extracts an existing slot."""
    fitz = pytest.importorskip("fitz")
    src = tmp_path / "nul.pdf"
    doc = fitz.open()
    page = doc.new_page()
    for row in range(25):
        page.insert_text((72, 72 + 14 * row), "clean text line. " * 4)
    doc.save(str(src))
    doc.close()
    meta = shelf.add_paper(tmp_path, src, project=_PROJECT)
    tp = shelf.text_path(tmp_path, meta.id)
    assert b"\x00" not in tp.read_bytes()
    # Simulate a legacy NUL-bearing extraction; --force re-extracts.
    tp.write_bytes(tp.read_bytes() + b"\x00tail")
    meta2 = shelf.add_paper(tmp_path, src, project=_PROJECT, force=True)
    assert meta2.id == meta.id
    assert b"\x00" not in tp.read_bytes()


def test_scanned_pdf_fails_loud(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    src = tmp_path / "scanned.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page()  # image-less, text-less pages
    doc.save(str(src))
    doc.close()
    with pytest.raises(shelf.ScannedPdfError, match="scanned"):
        shelf.add_paper(tmp_path, src, project=_PROJECT)
    # Fail-loud means no half-shelved residue.
    assert shelf.list_papers(tmp_path) == []


def test_map_staleness_binding(tmp_path: Path) -> None:
    meta = _add_text_paper(tmp_path, "content v1\n")
    mp = shelf.map_path(tmp_path, meta.id)
    # No map → not stale (absent ≠ stale).
    assert not shelf.map_is_stale(tmp_path, meta.id)
    mp.write_text(f"---\npaper: {meta.id}\ntext_sha: {meta.text_sha}\n"
                  f"---\n\n## Structure\n", encoding="utf-8")
    assert not shelf.map_is_stale(tmp_path, meta.id)
    # Re-extraction changes text.md → sha drifts → stale.
    mp.write_text("---\npaper: x\ntext_sha: 000000000000\n---\n\nold\n",
                  encoding="utf-8")
    assert shelf.map_is_stale(tmp_path, meta.id)


# ---------------------------------------------------------------------
# index
# ---------------------------------------------------------------------

def test_index_small_doc_exemption_no_spawn(tmp_path: Path,
                                            monkeypatch) -> None:
    meta = _add_text_paper(tmp_path, "tiny\n")

    def _boom(**kw):  # pragma: no cover
        raise AssertionError("spawn must not run for exempt docs")
    monkeypatch.setattr(agent_pkg, "spawn_llm", _boom)
    out = paper_index.generate_index(
        tmp_path, meta.id, prompt_dir=_PROMPT_DIR)
    assert out is None
    assert not shelf.map_path(tmp_path, meta.id).exists()


def test_index_generate_stamps_framework_frontmatter(tmp_path: Path,
                                                     monkeypatch) -> None:
    meta = _add_text_paper(tmp_path, "x" * (shelf.INDEX_MIN_CHARS + 10))
    mp = shelf.map_path(tmp_path, meta.id)

    def _fake_spawn(**kw):
        # Agent writes a map WITH its own (untrusted) frontmatter.
        mp.write_text("---\ntext_sha: agent-lies\n---\n\n## Structure\n"
                      "- [p.1] theorem 1: main\n", encoding="utf-8")
    monkeypatch.setattr(agent_pkg, "spawn_llm", _fake_spawn)
    out = paper_index.generate_index(
        tmp_path, meta.id, prompt_dir=_PROMPT_DIR)
    assert out == mp
    body = mp.read_text(encoding="utf-8")
    # Framework stamp is the only frontmatter; agent's is stripped.
    assert f"text_sha: {meta.text_sha}" in body
    assert "agent-lies" not in body
    assert "## Structure" in body
    assert not shelf.map_is_stale(tmp_path, meta.id)


def test_index_missing_map_is_loud(tmp_path: Path, monkeypatch) -> None:
    meta = _add_text_paper(tmp_path, "x" * (shelf.INDEX_MIN_CHARS + 10))
    monkeypatch.setattr(agent_pkg, "spawn_llm", lambda **kw: None)
    with pytest.raises(RuntimeError, match="without writing"):
        paper_index.generate_index(
            tmp_path, meta.id, prompt_dir=_PROMPT_DIR)


# ---------------------------------------------------------------------
# DB paper bindings + Context section
# ---------------------------------------------------------------------

def _pi(problem: str = "p") -> intent.ProblemIntent:
    return intent.ProblemIntent(problem=problem, charter="s")


def _bound_conn(problem: str = "p"):
    """In-memory DB with `problem` registered on the `_PROJECT` shelf —
    bindings live in `problem_papers` (v40: the Manifest `paper:`
    frontmatter is gone), and the Project is what says WHERE the bound
    paper is (§3.9)."""
    from Tooling.state import db as _db
    conn = _db.connect(":memory:")
    _db.init_schema(conn)
    conn.execute("INSERT OR IGNORE INTO projects (name, description,"
                 " created_at) VALUES (?, '', ?)", (_PROJECT, _db.now()))
    conn.execute("INSERT INTO problems (name, project, created_at)"
                 " VALUES (?, ?, ?)", (problem, _PROJECT, _db.now()))
    conn.commit()
    return conn


def test_section_paper_index_gating_and_shapes(tmp_path: Path) -> None:
    from Tooling.agent import context as ctx
    from Tooling.state import db as _db
    conn = _bound_conn()
    # No binding (and no conn at all) → no section.
    assert ctx._section_paper_index(_pi(), tmp_path) == []
    assert ctx._section_paper_index(_pi(), tmp_path, conn) == []
    # Binding to a missing shelf slot → loud placeholder, not a crash.
    _db.bind_paper(conn, problem="p", paper_id="deadbeef0000",
                   origin="manifest")
    lines = ctx._section_paper_index(_pi(), tmp_path, conn)
    assert any("missing" in ln for ln in lines)
    _db.unbind_paper(conn, problem="p", paper_id="deadbeef0000")
    # Small doc, no map → pointer to text.md.
    meta = _add_text_paper(tmp_path, "short paper\n")
    _db.bind_paper(conn, problem="p", paper_id=meta.id, origin="manifest")
    lines = ctx._section_paper_index(_pi(), tmp_path, conn)
    joined = "\n".join(lines)
    assert "No navigation map" in joined and "text.md" in joined
    # With a map → inlined; over-cap → loud truncation marker.
    shelf.map_path(tmp_path, meta.id).write_text(
        f"---\npaper: {meta.id}\ntext_sha: {meta.text_sha}\n---\n\n"
        + "## Structure\n" + ("- [p.1] lemma\n" * 2000),
        encoding="utf-8")
    joined = "\n".join(ctx._section_paper_index(_pi(), tmp_path, conn))
    assert "TRUNCATED at Context cap" in joined
    assert len(joined) < ctx.PAPER_INDEX_MAX_CHARS + 600


def test_section_paper_index_map_goes_to_companion(tmp_path: Path) -> None:
    """2026-07-14 (user call): the static navigation map repeated ~4KB
    into every context for 140+ wakes. With an attempts_dir the map
    body moves to the PAPER_MAP.md companion; inline keeps the pointer.
    No attempts_dir (legacy caller) → old inline behavior (pinned by
    test_section_paper_index_gating_and_shapes)."""
    from Tooling.agent import context as ctx
    from Tooling.state import db as _db
    conn = _bound_conn()
    meta = _add_text_paper(tmp_path, "short paper\n")
    _db.bind_paper(conn, problem="p", paper_id=meta.id, origin="manifest")
    map_body = (f"---\npaper: {meta.id}\ntext_sha: {meta.text_sha}\n---\n\n"
                "## Structure\n- [p.1] lemma X\n")
    shelf.map_path(tmp_path, meta.id).write_text(map_body, encoding="utf-8")
    attempts = tmp_path / ".attempts" / "x"
    attempts.mkdir(parents=True)
    joined = "\n".join(ctx._section_paper_index(
        _pi(), tmp_path, conn, attempts_dir=attempts))
    assert ctx.PAPER_MAP_COMPANION in joined
    assert "- [p.1] lemma X" not in joined  # body not inline
    companion = (attempts / ctx.PAPER_MAP_COMPANION).read_text(
        encoding="utf-8")
    assert "- [p.1] lemma X" in companion


def test_strategist_paper_section_carries_paper_ref_instruction(
        tmp_path: Path) -> None:
    """Phase 2: the MarkDeliverable provenance instruction is a
    CONDITIONAL Context line (paper-bound only), never a static-prompt
    edit (prompt-editing principle)."""
    from Tooling.agent import phase2_context as p2
    from Tooling.state import db as _db
    conn = _bound_conn()
    assert p2._section_paper_index_strategist(_pi(), tmp_path, conn) == []
    meta = _add_text_paper(tmp_path, "short paper\n")
    _db.bind_paper(conn, problem="p", paper_id=meta.id, origin="manifest")
    joined = "\n".join(
        p2._section_paper_index_strategist(_pi(), tmp_path, conn))
    assert "paper_ref" in joined and "MarkDeliverable" in joined


def test_review_paper_line_ref_and_missing(tmp_path: Path) -> None:
    """Phase 2 review render: recorded paper_ref → shown; paper-bound
    without a ref → loud locate-yourself placeholder; unbound → ''."""
    import json
    import sqlite3
    from Tooling.quality.review import _deliverable_paper_line
    from Tooling.state import db as _db
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES "
        "('Test.px', '2026-07-06T00:00:00+00:00')")
    _db.bind_paper(conn, problem="Test.px", paper_id="abc123",
                   origin="manifest")
    gid = _db.insert_goal(
        conn, problem="Test.px", slug="claim_a",
        lean_path="Problems/Test/px/proofs/L_claim_a.lean",
        statement="S", origin="forward", depth=0)
    g = conn.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
    # No MarkDeliverable row yet → loud placeholder.
    line = _deliverable_paper_line(conn, tmp_path, g, papers_cache={})
    assert "no paper_ref recorded" in line
    # Recorded ref → rendered.
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, payload, created_at,"
        " updated_at) VALUES ('Test.px', 0, 'routine', 'MarkDeliverable',"
        " ?, ?, '2026-07-06T00:00:00+00:00', '2026-07-06T00:00:00+00:00')",
        (gid, json.dumps({"paper_ref": "p.19 trace trichotomy"})))
    line = _deliverable_paper_line(conn, tmp_path, g, papers_cache={})
    assert "p.19 trace trichotomy" in line and "abc123" in line
    # Unbound problem → ''.
    _db.unbind_paper(conn, problem="Test.px", paper_id="abc123")
    line = _deliverable_paper_line(conn, tmp_path, g, papers_cache={})
    assert line == ""


# ---------------------------------------------------------------------
# v2: curated network commands (search / fetch) — network stubbed
# ---------------------------------------------------------------------

def _mk_pdf_bytes() -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    for row in range(25):
        page.insert_text((72, 72 + 14 * row), "fetched text line. " * 4)
    data = doc.tobytes()
    doc.close()
    return data


def test_arxiv_id_resolution_old_and_new_style() -> None:
    from Tooling.papers.fetch import _resolve_url
    assert _resolve_url("2605.23679") == "https://arxiv.org/pdf/2605.23679"
    assert _resolve_url("math/0601146") \
        == "https://arxiv.org/pdf/math/0601146"
    assert _resolve_url("math.GT/0601146v2") \
        == "https://arxiv.org/pdf/math.GT/0601146v2"
    # A non-id passes through untouched (URL path).
    assert _resolve_url("https://arxiv.org/pdf/x").endswith("/pdf/x")


def test_fetch_refuses_non_whitelisted_host(tmp_path: Path) -> None:
    # (www.ams.org joined the whitelist 2026-08-05 — publisher-run open
    # archives; a random host still refuses.)
    from Tooling.papers import fetch
    with pytest.raises(ValueError, match="not fetch-whitelisted"):
        fetch.fetch_and_shelve(tmp_path, "https://evil.example.com/x.pdf",
                               problem=None, reason=None)


def test_fetch_whitelist_covers_cambridge() -> None:
    # 2026-08-22 (user call): Cambridge Core hosts the free CMS journal
    # backfiles — Moser's CMB 1963 paper was structurally unfetchable
    # without it (same publisher-open-archive shape as the AMS entry).
    from Tooling.papers import fetch
    assert "www.cambridge.org" in fetch.FETCH_HOST_WHITELIST
    assert "cambridge.org" in fetch.FETCH_HOST_WHITELIST


def test_fetch_doi_refusal_names_the_way_out(tmp_path: Path) -> None:
    # doi.org is a redirector; the refusal must point at a move the
    # agent can actually make (paper_search(doi=…)), not just recite
    # the whitelist — Erdos.p1's scholar held a DOI whose open copy
    # sat on whitelisted ams.org and was taught nothing.
    from Tooling.papers import fetch
    with pytest.raises(ValueError, match=r'paper_search\(doi='):
        fetch.fetch_and_shelve(
            tmp_path, "https://doi.org/10.1090/s0002-9939-96-03653-2",
            problem=None, reason=None)


def test_search_enriches_doi_only_hits_via_unpaywall(monkeypatch) -> None:
    # The query path must join its own two halves: a DOI-only hit and
    # the unpaywall lookup living in the same module. (Erdos.p1: the
    # exact target came back DOI-only while unpaywall held its ams.org
    # PDF — the scholar was left to fetch doi.org and be refused.)
    import io
    import json as _json
    from contextlib import redirect_stdout

    from Tooling.papers import search
    monkeypatch.setattr(search, "_openalex", lambda q: [
        {"source": "openalex", "title": "other", "doi": "10.1/other",
         "pdf_url": "https://arxiv.org/pdf/1.1"}])
    monkeypatch.setattr(search, "_arxiv", lambda q: [])
    monkeypatch.setattr(search, "_crossref", lambda q: [
        {"source": "crossref", "title": "target", "doi": "10.2/target"}])
    seen: list[str] = []
    monkeypatch.setattr(search, "_unpaywall", lambda doi: (
        seen.append(doi) or [
            {"source": "unpaywall", "host_type": "publisher",
             "pdf_url": "https://www.ams.org/x.pdf"}]))
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert search.main(["some", "query"]) == 0
    hits = _json.loads(buf.getvalue())
    target = next(h for h in hits if h["title"] == "target")
    assert target["pdf_url"] == "https://www.ams.org/x.pdf"
    assert target["pdf_via"] == "unpaywall"
    # rows that already carry a pdf_url are not re-looked-up
    assert seen == ["10.2/target"]


def test_fetch_refuses_non_pdf_response(tmp_path: Path,
                                        monkeypatch) -> None:
    from Tooling.papers import fetch
    import io

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: _R(b"<html>interstitial</html>"))
    with pytest.raises(RuntimeError, match="not a PDF"):
        fetch.fetch_and_shelve(tmp_path, "2605.23679",
                               problem="Test.px", reason=None)


def test_fetch_without_a_problem_names_the_shelf_it_needs(
        tmp_path: Path) -> None:
    """§3.9: there is no workspace-global shelf any more, so a fetch
    with no problem has nowhere to land. The refusal names the argument
    that makes it work rather than inventing a home."""
    from Tooling.papers import fetch
    with pytest.raises(ValueError, match="problem"):
        fetch.fetch_and_shelve(tmp_path, "2605.23679",
                               problem=None, reason=None)


def test_fetch_shelves_and_binds(tmp_path: Path, monkeypatch) -> None:
    """arXiv id → resolved URL → shelved via content hash → bound with
    the calling seat as origin ('agent' when no ASTERISM_SEAT env —
    the hardcoded 'scholar' mislabelled a strategist's direct fetch,
    2026-08-22). Uses a real (tiny) PDF so extraction runs."""
    import io
    import sqlite3
    from Tooling.papers import fetch, shelf
    from Tooling.state import db as _db
    pdf = _mk_pdf_bytes()

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: _R(pdf))
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES"
        " ('Test.px', 'ts')")
    conn.commit()
    conn.close()

    pid = fetch.fetch_and_shelve(tmp_path, "2605.23679",
                                 problem="Test.px", reason="cited [X]")
    assert shelf.text_path(tmp_path, pid).is_file()
    meta = shelf.load_meta(tmp_path, pid)
    assert meta.source_name == "arxiv_2605.23679.pdf"  # no temp-name leak
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    rows = _db.paper_bindings(conn, "Test.px")
    assert [(r["paper_id"], r["origin"]) for r in rows] \
        == [(pid, "agent")]
    conn.close()


def test_fetch_cap_enforced(tmp_path: Path, monkeypatch) -> None:
    import sqlite3
    from Tooling.papers import fetch
    from Tooling.state import db as _db
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES"
        " ('Test.px', 'ts')")
    for i in range(fetch.MAX_SCHOLAR_FETCHES_PER_PROBLEM):
        _db.bind_paper(conn, problem="Test.px", paper_id=f"p{i}",
                       origin="scholar")
    conn.close()
    with pytest.raises(RuntimeError, match="fetch cap"):
        fetch.fetch_and_shelve(tmp_path, "2605.23679",
                               problem="Test.px", reason=None)


def test_search_aggregates_sources(monkeypatch) -> None:
    from Tooling.papers import search
    monkeypatch.setattr(search, "_get_json", lambda url: {
        "results": [{"title": "T", "publication_year": 1982,
                     "doi": "https://doi.org/10.1/x",
                     "open_access": {"oa_status": "diamond"},
                     "best_oa_location": {"pdf_url": "https://a/x.pdf"}}]
    } if "openalex" in url else {
        "message": {"items": [{"title": ["T2"], "DOI": "10.2/y",
                               "issued": {"date-parts": [[1990]]}}]}})
    monkeypatch.setattr(search, "_get_text", lambda url: (
        "<entry><id>http://arxiv.org/abs/2605.23679v1</id>"
        "<title>Geo</title><published>2026-05-22</published></entry>"))
    hits = (search._openalex("q") + search._arxiv("q")
            + search._crossref("q"))
    srcs = [h["source"] for h in hits]
    assert srcs == ["openalex", "arxiv", "crossref"]
    assert hits[1]["arxiv_id"] == "2605.23679v1"
    assert hits[1]["pdf_url"].endswith("/pdf/2605.23679v1")


# ---------------------------------------------------------------------
# v2: FetchPaper decision + Scholar pipeline (spawn stubbed)
# ---------------------------------------------------------------------

def _v2_conn(tmp_path: Path):
    import sqlite3
    from Tooling.state import db as _db
    conn = sqlite3.connect(str(tmp_path / "asterism.db"))
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at) VALUES"
        " ('Test.px', 'ts')")
    conn.commit()
    return conn


def test_fetchpaper_decision_kind_is_retired(tmp_path: Path) -> None:
    """FetchPaper retired 2026-08-22 (owner ruling): the Strategist
    fetches directly via paper_search/paper_fetch — the decision kind
    stays recognized so the gate TEACHES the replacement."""
    from Tooling.pipeline.strategist import Decision, verify_decision
    conn = _v2_conn(tmp_path)
    err = verify_decision(
        Decision(kind="FetchPaper", reason="need the JSJ statement",
                 payload={"query": "Thurston 1982"}),
        conn, problem="Test.px")
    assert "retired" in err and "paper_fetch" in err
    conn.close()


def test_release_own_leases_frees_claimed_rows(tmp_path: Path) -> None:
    """Graceful-exit sweep (frontend joint test 2026-07-07): a row
    claimed by this PID is released (not deleted); other owners' leases
    untouched."""
    import os
    from Tooling.state import db as _db
    conn = _v2_conn(tmp_path)
    _db.enqueue(conn, kind="Scholar", target_id="Test.px",
                target_kind="Problem", problem="Test.px")
    _db.enqueue(conn, kind="Scholar", target_id="Test.px",
                target_kind="Problem", problem="Test.px", priority=1)
    row = _db.pop_queue(conn)  # leases to os.getpid()
    assert row is not None
    conn.execute("UPDATE queue SET owner_pid = 99999999,"
                 " leased_at = 'ts' WHERE id != ?", (int(row["id"]),))
    conn.commit()
    assert _db.release_own_leases(conn) == 1
    mine, other = conn.execute(
        "SELECT COUNT(*) FROM queue WHERE owner_pid IS NULL"
    ).fetchone()[0], conn.execute(
        "SELECT COUNT(*) FROM queue WHERE owner_pid = 99999999"
    ).fetchone()[0]
    assert mine == 1 and other == 1
    assert os.getpid()  # documents the implicit owner
    conn.close()


def test_section_paper_index_multi_paper(tmp_path: Path) -> None:
    """D14: primary (manifest-origin binding) full; scholar-fetched
    papers as one-line auxiliary entries."""
    from Tooling.agent import context as ctx
    from Tooling.state import db as _db
    conn = _v2_conn(tmp_path)
    meta1 = _add_text_paper(tmp_path, "primary paper\n", name="prim.md")
    meta2 = _add_text_paper(tmp_path, "aux paper\n", name="aux.md")
    _db.bind_paper(conn, problem="Test.px", paper_id=meta2.id,
                   origin="scholar", reason="cited")
    _db.bind_paper(conn, problem="Test.px", paper_id=meta1.id,
                   origin="manifest")
    joined = "\n".join(ctx._section_paper_index(
        _pi("Test.px"), tmp_path, conn))
    assert "prim.md" in joined
    assert "### Auxiliary papers" in joined
    assert f"papers/{meta2.id}" in joined and "aux.md" in joined
    conn.close()


def test_section_paper_index_stale_map_warns(tmp_path: Path) -> None:
    from Tooling.agent import context as ctx
    from Tooling.state import db as _db
    conn = _bound_conn()
    meta = _add_text_paper(tmp_path, "short paper\n")
    _db.bind_paper(conn, problem="p", paper_id=meta.id, origin="manifest")
    shelf.map_path(tmp_path, meta.id).write_text(
        "---\npaper: x\ntext_sha: 000000000000\n---\n\n## Structure\n",
        encoding="utf-8")
    joined = "\n".join(ctx._section_paper_index(_pi(), tmp_path, conn))
    assert "older extraction" in joined
