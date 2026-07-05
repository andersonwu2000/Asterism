"""Paper pipeline Phase 1 (docs/internal/paper_pipeline_design.md):
shelf identity/extraction, index staleness binding, small-doc
exemption, Manifest `paper:` field, Context paper-index section."""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling import agent as agent_pkg
from Tooling.papers import index as paper_index
from Tooling.papers import shelf
from Tooling.state import manifest


# ---------------------------------------------------------------------
# shelf
# ---------------------------------------------------------------------

def _add_text_paper(ws: Path, body: str, name: str = "notes.md"):
    src = ws / name
    src.write_text(body, encoding="utf-8")
    return shelf.add_paper(ws, src)


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


def test_add_paper_rejects_unknown_format(tmp_path: Path) -> None:
    src = tmp_path / "paper.docx"
    src.write_bytes(b"not a pdf")
    with pytest.raises(ValueError, match="unsupported paper format"):
        shelf.add_paper(tmp_path, src)


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
    meta = shelf.add_paper(tmp_path, src)
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
    meta = shelf.add_paper(tmp_path, src)
    tp = shelf.text_path(tmp_path, meta.id)
    assert b"\x00" not in tp.read_bytes()
    # Simulate a legacy NUL-bearing extraction; --force re-extracts.
    tp.write_bytes(tp.read_bytes() + b"\x00tail")
    meta2 = shelf.add_paper(tmp_path, src, force=True)
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
        shelf.add_paper(tmp_path, src)
    # Fail-loud means no half-shelved residue.
    assert not shelf.papers_root(tmp_path).exists() or not any(
        shelf.papers_root(tmp_path).iterdir())


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
        tmp_path, meta.id,
        prompt_dir=Path("Tooling/prompts").resolve())
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
        tmp_path, meta.id, prompt_dir=Path("Tooling/prompts").resolve())
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
            tmp_path, meta.id, prompt_dir=Path("Tooling/prompts").resolve())


# ---------------------------------------------------------------------
# Manifest `paper:` + Context section
# ---------------------------------------------------------------------

def _mfst(paper: str = "") -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="s", paper=paper)


def test_manifest_parses_paper_pointer(tmp_path: Path) -> None:
    p = tmp_path / "Manifest.md"
    p.write_text("---\nproblem: p\npaper: abc123def456\n---\n\n"
                 "# t\n\n## Statement\nS\n", encoding="utf-8")
    m = manifest.parse(p)
    assert m.paper == "abc123def456"


def test_section_paper_index_gating_and_shapes(tmp_path: Path) -> None:
    from Tooling.agent import context as ctx
    # No pointer → no section.
    assert ctx._section_paper_index(_mfst(""), tmp_path) == []
    # Pointer to a missing shelf slot → loud placeholder, not a crash.
    lines = ctx._section_paper_index(_mfst("deadbeef0000"), tmp_path)
    assert any("missing" in ln for ln in lines)
    # Small doc, no map → pointer to text.md.
    meta = _add_text_paper(tmp_path, "short paper\n")
    lines = ctx._section_paper_index(_mfst(meta.id), tmp_path)
    joined = "\n".join(lines)
    assert "No navigation map" in joined and "text.md" in joined
    # With a map → inlined; over-cap → loud truncation marker.
    shelf.map_path(tmp_path, meta.id).write_text(
        f"---\npaper: {meta.id}\ntext_sha: {meta.text_sha}\n---\n\n"
        + "## Structure\n" + ("- [p.1] lemma\n" * 2000),
        encoding="utf-8")
    joined = "\n".join(ctx._section_paper_index(_mfst(meta.id), tmp_path))
    assert "TRUNCATED at Context cap" in joined
    assert len(joined) < ctx.PAPER_INDEX_MAX_CHARS + 600


def test_strategist_paper_section_carries_paper_ref_instruction(
        tmp_path: Path) -> None:
    """Phase 2: the MarkDeliverable provenance instruction is a
    CONDITIONAL Context line (paper-bound only), never a static-prompt
    edit (prompt-editing principle)."""
    from Tooling.agent import phase2_context as p2
    assert p2._section_paper_index_strategist(_mfst(""), tmp_path) == []
    meta = _add_text_paper(tmp_path, "short paper\n")
    joined = "\n".join(
        p2._section_paper_index_strategist(_mfst(meta.id), tmp_path))
    assert "paper_ref" in joined and "MarkDeliverable" in joined


def test_review_paper_line_ref_and_missing(tmp_path: Path) -> None:
    """Phase 2 review render: recorded paper_ref → shown; paper-bound
    without a ref → loud locate-yourself placeholder; unbound → ''."""
    import json
    import sqlite3
    from Tooling.core.cli import _deliverable_paper_line
    from Tooling.state import db as _db
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES "
        "('Test.px', 'Problems/Test/px/Manifest.md',"
        " '2026-07-06T00:00:00+00:00')")
    pdir = _db.problem_dir(tmp_path, "Test.px")
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: Test.px\npaper: abc123\n---\n\n# t\n",
        encoding="utf-8")
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
    (pdir / "Manifest.md").write_text(
        "---\nproblem: Test.px\n---\n\n# t\n", encoding="utf-8")
    line = _deliverable_paper_line(conn, tmp_path, g, papers_cache={})
    assert line == ""


def test_section_paper_index_stale_map_warns(tmp_path: Path) -> None:
    from Tooling.agent import context as ctx
    meta = _add_text_paper(tmp_path, "short paper\n")
    shelf.map_path(tmp_path, meta.id).write_text(
        "---\npaper: x\ntext_sha: 000000000000\n---\n\n## Structure\n",
        encoding="utf-8")
    joined = "\n".join(ctx._section_paper_index(_mfst(meta.id), tmp_path))
    assert "older extraction" in joined
