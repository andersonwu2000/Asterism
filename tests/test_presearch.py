"""target-1 v1 pre-search (`Tooling/pipeline/_presearch.py`) unit tests.

Cover the framework-side 3-block verification + render + Context injection.
The agent spawn itself is exercised live, not here."""
from Tooling.pipeline import _presearch
from Tooling.agent import context


class _Info:
    def __init__(self, found, sig):
        self.found = found
        self.signature = sig


def test_verify_drops_hallucinated_mathlib(monkeypatch, tmp_path):
    """A Mathlib name that doesn't `#check` (found=False) is dropped."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(
        lemma_lookup, "lookup_batch",
        lambda names, ws: {"Real.add_comm": _Info(True, "sig"),
                           "Bogus.lemma": _Info(False, "")})
    blocks = {"mathlib": [{"name": "Real.add_comm"}, {"name": "Bogus.lemma"}]}
    names = [c["name"] for c in _presearch._verify(blocks, tmp_path, tmp_path)]
    assert "Real.add_comm" in names
    assert "Bogus.lemma" not in names


def test_verify_keeps_when_lookup_unavailable(monkeypatch, tmp_path):
    """Offline / lake hiccup: keep Mathlib candidates unverified (best-effort)."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(
        lemma_lookup, "lookup_batch",
        lambda names, ws: (_ for _ in ()).throw(RuntimeError("offline")))
    assert _presearch._verify(
        {"mathlib": [{"name": "Real.add_comm"}]}, tmp_path, tmp_path)


def test_verify_library_against_db_index(tmp_path):
    """Library candidates are kept only when among the DB's placed+bridged
    decl names (v18 — exact FQN or leaf match; was an INDEX.md substring
    probe). conn=None keeps all (defensive fallback)."""
    from Tooling.state import db as _dbm
    conn = _dbm.connect(":memory:")
    _dbm.init_schema(conn)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("INSERT INTO problems (name, created_at,"
                 " bootstrap_done) VALUES ('p','t',1)")
    conn.execute("INSERT INTO library_decls (problem, slug, target_name,"
                 " target_file, lifecycle, created_at, updated_at)"
                 " VALUES ('p','real_thing','Library.X.real_thing',"
                 "'Library/X.lean','migrated','t','t')")
    _dbm.mark_library_bridged(conn, "p")
    blocks = {"library": [{"name": "Library.X.real_thing"},
                          {"name": "Library.X.ghost"}]}
    names = [c["name"] for c in _presearch._verify(blocks, tmp_path, tmp_path,
                                                   conn=conn)]
    assert "Library.X.real_thing" in names
    assert "Library.X.ghost" not in names
    # module-qualified report with matching LEAF also passes
    blocks = {"library": [{"name": "Library.Other.Path.real_thing"}]}
    assert _presearch._verify(blocks, tmp_path, tmp_path, conn=conn)
    # conn=None -> keep all (no filter available)
    blocks = {"library": [{"name": "Library.X.ghost"}]}
    assert _presearch._verify(blocks, tmp_path, tmp_path)


def test_verify_in_problem_existence_guard(tmp_path):
    """In-problem names are kept only if their decl appears in `proofs/` — a
    light guard against padded / invented sibling names."""
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "L_real_sib.lean").write_text(
        "theorem real_sib : True := trivial\n", encoding="utf-8")
    blocks = {"in_problem": [{"name": "Problems.p.real_sib"},
                             {"name": "Problems.p.ghost_sib"}]}
    names = [c["name"] for c in _presearch._verify(blocks, tmp_path, pdir)]
    assert "Problems.p.real_sib" in names
    assert "Problems.p.ghost_sib" not in names


def test_verify_caps_each_block(tmp_path):
    """Each block is capped at `_MAX_PER_BLOCK` (no INDEX → library kept as-is,
    so the per-block cap is what limits the count)."""
    (tmp_path / "Library").mkdir()
    blocks = {"library": [{"name": f"Library.X.n{i}"} for i in range(25)]}
    out = _presearch._verify(blocks, tmp_path, tmp_path)
    assert len(out) == _presearch._MAX_PER_BLOCK


def test_verify_orders_in_problem_library_mathlib(monkeypatch, tmp_path):
    """Output is ordered in_problem → library → mathlib (cleanest cite first)."""
    from Tooling.knowledge import lemma_lookup
    monkeypatch.setattr(lemma_lookup, "lookup_batch",
                        lambda names, ws: {"Real.x": _Info(True, "s")})
    (tmp_path / "Library").mkdir()
    (tmp_path / "Library" / "INDEX.md").write_text(
        "- `Library.Y.z`\n", encoding="utf-8")
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "L_sib.lean").write_text(
        "theorem sib : True := trivial\n", encoding="utf-8")
    blocks = {"mathlib": [{"name": "Real.x"}],
              "library": [{"name": "Library.Y.z"}],
              "in_problem": [{"name": "Problems.p.sib"}]}
    srcs = [c["source"] for c in _presearch._verify(blocks, tmp_path, pdir)]
    assert srcs == ["in_problem", "library", "mathlib"]


def test_section_present_when_cache_exists(tmp_path):
    """`_section_presearch_candidates` injects the cache when present, [] absent."""
    pdir = tmp_path / "Problems" / "p"
    (pdir / ".presearch").mkdir(parents=True)
    _presearch.presearch_path(pdir, 7).write_text(
        "## Candidate lemmas\n\n- `Foo.bar`\n", encoding="utf-8")
    out = context._section_presearch_candidates(pdir, 7)
    assert out and "Candidate lemmas" in "\n".join(out)
    assert context._section_presearch_candidates(pdir, 999) == []


def test_claim_from_brief_prefers_declarations_over_hints():
    """The mint has no goal row, so its search key comes off the Inject
    brief (2026-08-07). `## Declarations` (exact Lean) wins, and
    `## Strategy & Hints` must NOT ride along — feeding the searcher the
    Strategist's guessed route biases it away from the statement."""
    brief = (
        "Roadmap: entry\n\n## Need\nMint brick `L_foo_bar` in `proofs/...`.\n\n"
        "## Declarations\n`theorem foo_bar (n : Nat) : n + 0 = n`\n\n"
        "## Strategy & Hints\nUse `Nat.add_zero`; try `simp`.\n")
    claim = _presearch.claim_from_brief(brief)
    assert "theorem foo_bar" in claim
    assert "Nat.add_zero" not in claim
    assert "Mint brick" not in claim


def test_claim_from_brief_falls_back_to_claim_then_whole_brief():
    assert "F.card" in _presearch.claim_from_brief(
        "## Need\nx\n\n## Claim\nFor union-closed F: F.card ≤ 2 * k\n")
    assert _presearch.claim_from_brief("no sections here") == "no sections here"
    assert _presearch.claim_from_brief("") == ""


def test_slug_from_brief_strips_the_file_prefix():
    assert _presearch.slug_from_brief(
        "## Need\nMint brick `L_foo_bar` in `proofs/L_foo_bar.lean`.") == "foo_bar"
    assert _presearch.slug_from_brief("Mint brick `plain_slug`.") == "plain_slug"
    assert _presearch.slug_from_brief("nothing here") == ""


def test_adopt_for_goal_hands_the_mint_search_to_the_prove_step(tmp_path):
    """One pre-search per brick (user call 2026-08-07): the mint runs it
    keyed on its Inject, and the goal it creates inherits the cache, so
    `ensure_presearch` on that goal hits instead of spawning a second
    search."""
    pdir = tmp_path / "Problems" / "p"
    (pdir / ".presearch").mkdir(parents=True)
    src = _presearch.mint_presearch_path(pdir, 42)
    src.write_text("## Candidate lemmas\n\n- `Foo.bar`\n", encoding="utf-8")

    _presearch.adopt_for_goal(pdir, 42, 7)

    assert not src.exists()
    dst = _presearch.presearch_path(pdir, 7)
    assert "Foo.bar" in dst.read_text(encoding="utf-8")
    # the goal arm now cache-hits: no spawn, even with the module's
    # spawn entry point left untouched
    assert _presearch.ensure_presearch(
        goal={"id": 7, "statement": "x = x", "slug": "s", "problem": "p"},
        workspace=tmp_path, problem_dir=pdir, attempts_dir=tmp_path,
        prompt_dir=tmp_path) == dst


def test_adopt_for_goal_never_clobbers_an_existing_goal_cache(tmp_path):
    pdir = tmp_path / "Problems" / "p"
    (pdir / ".presearch").mkdir(parents=True)
    _presearch.mint_presearch_path(pdir, 42).write_text("mint", encoding="utf-8")
    _presearch.presearch_path(pdir, 7).write_text("goal", encoding="utf-8")
    _presearch.adopt_for_goal(pdir, 42, 7)
    assert _presearch.presearch_path(pdir, 7).read_text(encoding="utf-8") == "goal"


def test_verify_attaches_sibling_status_and_statement(tmp_path):
    """agent_feedback 2026-07-09/10 (91 entries): in-problem candidates
    carry their DB status + a one-line statement, so a DISPROVED sibling
    can never be mistaken for a citable fact."""
    from Tooling.state import db as _dbm
    conn = _dbm.connect(":memory:")
    _dbm.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at)"
                 " VALUES ('p','t')")
    for slug, status in (("sib_proved", "proved"),
                         ("sib_false", "disproved")):
        gid = _dbm.insert_goal(
            conn, problem="p", slug=slug,
            lean_path=f"Problems/p/proofs/L_{slug}.lean",
            statement=f"∀ n : ℕ, {slug} n", origin="backward")
        conn.execute("UPDATE goals SET status=? WHERE id=?", (status, gid))
    conn.commit()
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "L_x.lean").write_text(
        "theorem sib_proved : True := trivial\n"
        "theorem sib_false : False := by sorry\n", encoding="utf-8")
    blocks = {"in_problem": [{"name": "sib_proved"}, {"name": "sib_false"}]}
    out = _presearch._verify(blocks, tmp_path, pdir, conn=conn, problem="p")
    by_name = {e["name"]: e for e in out}
    assert by_name["sib_proved"]["status"] == "proved"
    assert by_name["sib_false"]["status"] == "disproved"
    assert "sib_false n" in by_name["sib_false"]["statement"]
    # render: proved stays lowercase, non-proved shouts; header carries
    # the citability rule; statement rendered as an indented line
    section = _presearch._render_section(out)
    assert "[this problem, proved]" in section
    assert "[this problem, DISPROVED]" in section
    assert "statement is FALSE" in section
    assert "∀ n : ℕ, sib_false n" in section


def test_verify_without_conn_stays_names_only(tmp_path):
    """No conn / no problem name → enrichment silently absent (old shape)."""
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "L_s.lean").write_text(
        "theorem s : True := trivial\n", encoding="utf-8")
    out = _presearch._verify({"in_problem": [{"name": "s"}]}, tmp_path, pdir)
    assert out and "status" not in out[0]
    section = _presearch._render_section(out)
    assert "[this problem]" in section
    assert "statement is FALSE" not in section  # no status → no rule line


def test_dry_section_is_explicit():
    """Ran-but-dry renders an explicit section (an absent section is
    indistinguishable from 'presearch never ran')."""
    assert "NO candidates" in _presearch._DRY_SECTION
    assert _presearch._DRY_SECTION.startswith("## Candidate lemmas")


def test_verify_excludes_goal_own_slug(tmp_path):
    """2026-07-05 audit: the goal's OWN sorry stub sits in proofs/, so the
    in_problem hay check 'verified' it and the candidate list invited
    citing an open goal as if proved."""
    from Tooling.pipeline import _presearch
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "L_my_goal.lean").write_text(
        "theorem my_goal : True := by sorry\n"
        "theorem sibling_done : True := trivial\n", encoding="utf-8")
    blocks = {"in_problem": [
        {"name": "my_goal", "why": "matches"},
        {"name": "sibling_done", "why": "proved sibling"},
    ], "library": [], "mathlib": []}
    out = _presearch._verify(blocks, tmp_path, pdir, exclude_slug="my_goal")
    names = [e["name"] for e in out]
    assert "my_goal" not in names
    assert "sibling_done" in names


def test_render_section_status_note_citation_rule() -> None:
    """Task #123: citation is shape-derived — a non-proved sibling is
    citable on every path (auto-link + wait). The old three-mode note
    (Builder proved-only / leaf-bypass proved-only) must stay gone."""
    out = [{"name": "sib", "source": "sibling", "status": "attempting",
            "signature": "theorem sib : True"}]
    section = _presearch._render_section(out)
    assert "citable" in section and "auto-links" in section
    assert "leaf-bypass" not in section
    assert "Builder" not in section


def test_verify_marks_a_non_goal_name_instead_of_presenting_it_bare(tmp_path):
    """agent_feedback 2026-08-22: `s24234` (a strategy-internal name in
    a proofs/ file) passed the hay check, shipped bare, and a backward
    spawn burned a validation round importing `proofs.L_s24234`, which
    does not exist. A name the goals table does not know is flagged
    `not a goal`, and the section header says never to import one."""
    from Tooling.state import db as _dbm
    conn = _dbm.connect(":memory:")
    _dbm.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('p','t')")
    gid = _dbm.insert_goal(
        conn, problem="p", slug="sib_proved",
        lean_path="Problems/p/proofs/L_sib_proved.lean",
        statement="True", origin="backward")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (gid,))
    conn.commit()
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    (pdir / "proofs" / "_strategy_s24234.lean").write_text(
        "theorem sib_proved : True := trivial\n"
        "-- s24234 internal alias\n", encoding="utf-8")
    blocks = {"in_problem": [{"name": "sib_proved"}, {"name": "s24234"}]}
    out = _presearch._verify(blocks, tmp_path, pdir, conn=conn, problem="p")
    by_name = {e["name"]: e for e in out}
    assert by_name["sib_proved"]["status"] == "proved"
    assert by_name["s24234"]["status"] == "not a goal"
    section = _presearch._render_section(out)
    assert "NOT A GOAL" in section
    assert "never import it as a sibling proof file" in section
