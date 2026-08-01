"""state.programme — Programme store contract (research mode P1).

Guards: v30 table exists on fresh DBs; four-section proposal contract
(teaching rejections); Proof over-length warning (warn, never block);
revision chain semantics (passed rows advance rev, rejected rows keep
the candidate number + dialogue); rejection notice surfaces only while
the latest resolved row is a rejection; PROGRAMME.md render carries
rev header + reservations and no revision log.
"""
from pathlib import Path

from Tooling.state import db
from Tooling.state import programme


def _fresh(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at,"
              " bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _body(proof="The route holds because of X.",
          argument="Brick A unblocks the named vector.",
          roadmap="1. Re-prove s23259 without the exists."):
    return ("# Close the gcd gap\n"
            "## Argument\n" + argument + "\n"
            "## Proof\n" + proof + "\n"
            "## Roadmap\n" + roadmap + "\n")


# ---------------------------------------------------------------- parse

def test_parse_ok():
    sections, err = programme.parse_proposal(_body())
    assert err is None
    assert sections["title"] == "Close the gcd gap"
    assert "named vector" in sections["argument"]
    assert sections["proof"].startswith("The route holds")


def test_parse_missing_section_teaches():
    body = "# T\n## Argument\na\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "## Proof" in err


def test_parse_requires_title_line():
    body = "## Argument\na\n## Proof\np\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "# <Title>" in err


def test_parse_out_of_order_rejected():
    body = "# T\n## Proof\np\n## Argument\na\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "order" in err


def test_parse_duplicate_section_rejected():
    body = _body() + "## Roadmap\nagain\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "duplicate" in err


def test_parse_empty_section_rejected():
    body = "# T\n## Argument\na\n## Proof\n## Roadmap\nr\n"
    sections, err = programme.parse_proposal(body)
    assert sections is None and "## Proof" in err and "empty" in err


def test_length_warning_thresholds():
    """07-29 bloat ruling: three absolute surfaces — Proof (readability,
    most headroom), Argument (the observed bloat surface), package
    total. All warn-only, never a block."""
    ok, _ = programme.parse_proposal(_body())
    assert programme.length_warning(ok) is None

    long_proof, _ = programme.parse_proposal(
        _body(proof="x" * (programme.PROOF_WARN_CHARS + 1)))
    warn = programme.length_warning(long_proof)
    assert warn and "PROOF LENGTH WARNING" in warn
    assert "ARGUMENT" not in warn

    body = _body(argument="a" * (programme.ARGUMENT_WARN_CHARS + 1))
    long_arg, _ = programme.parse_proposal(body)
    warn = programme.length_warning(long_arg, body)
    assert warn and "ARGUMENT LENGTH WARNING" in warn
    assert "PROOF LENGTH" not in warn

    body = _body(roadmap="r" * (programme.DOC_WARN_CHARS + 1))
    long_doc, _ = programme.parse_proposal(body)
    warn = programme.length_warning(long_doc, body)
    assert warn and "PROPOSAL LENGTH WARNING" in warn


# ---------------------------------------------------------------- store

def test_rev_chain_and_rejection_rows(tmp_path):
    c = _fresh(tmp_path)
    assert programme.current_rev(c, "p") is None
    assert programme.next_rev_number(c, "p") == 1

    rev = programme.record_pass(
        c, "p", _body(), {"verdict": "pass", "reservations": []},
        [{"round": 1, "role": "adversary", "text": "pass"}], 1, "batch-1")
    assert rev == 1
    assert programme.current_rev(c, "p")["rev"] == 1

    # A rejected proposal aims at rev 2 but the chain does not advance.
    programme.record_rejection(
        c, "p", _body(), [{"round": 1, "role": "adversary",
                           "text": "refuted"}], 4)
    assert programme.current_rev(c, "p")["rev"] == 1
    assert programme.next_rev_number(c, "p") == 2

    notice = programme.rejection_notice(c, "p")
    assert notice and "rev 2" in notice and "4 round" in notice

    # A later pass clears the notice and advances the chain.
    rev2 = programme.record_pass(
        c, "p", _body(), {"verdict": "pass",
                          "reservations": ["watch the sign"]},
        [], 2, "batch-2")
    assert rev2 == 2
    assert programme.rejection_notice(c, "p") is None


def test_rejection_notice_absent_before_any_row(tmp_path):
    c = _fresh(tmp_path)
    assert programme.rejection_notice(c, "p") is None


# --------------------------------------------------------------- render

def test_render_none_before_bootstrap(tmp_path):
    c = _fresh(tmp_path)
    assert programme.render(c, "p", tmp_path) is None


def test_render_header_and_reservations(tmp_path):
    c = _fresh(tmp_path)
    programme.record_pass(
        c, "p", _body(), {"verdict": "pass",
                          "reservations": ["watch the sign"]},
        [], 1, "batch-1")
    path = programme.render(c, "p", tmp_path)
    assert path == tmp_path / "PROGRAMME.md"
    text = path.read_text(encoding="utf-8")
    assert "rev 1" in text
    assert "watch the sign" in text
    assert "DO NOT EDIT" in text
    assert "# Close the gcd gap" in text
    # No revision log in the render (design §2 round 8/11 ruling).
    assert "rev 0" not in text


# ------------------------------------------------- authorising revision

def _authorised_goal(c, *, slug, batch_id, decision_id, rev_body=None):
    """Land a rev on `batch_id` and a goal the batch's decision produced."""
    gid = db.insert_goal(c, problem="p", slug=slug,
                         lean_path=f"Problems/p/proofs/L_{slug}.lean",
                         statement=f"theorem {slug} : T", origin="forward",
                         depth=1, status="open")
    c.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, produced_goal_id,"
        " created_at, updated_at) VALUES ('p', 0, 'routine', 'Inject',"
        " ?, ?, ?, ?)", (batch_id, gid, db.now(), db.now()))
    c.commit()
    return gid


def test_rev_for_goal_pins_the_revision_that_authorised_the_work(tmp_path):
    """The defect: a worker was shown whatever the Programme had become,
    not the argument its goal was dispatched under. Branch B's sub-goals
    keep being auto-dispatched while branch A's review ships a new rev,
    so the Proof under the worker's feet changes with no decision and no
    signal — either a spurious `no_nl_correspondence` decline, or a
    silent re-anchor onto a different step.

    Measured on the live SG tree before the fix: seven goals authorised
    by revs 1/1/2/2/3/3/4, `current_rev` = 5 — every one of them would
    have been handed rev 5."""
    c = _fresh(tmp_path)
    programme.record_pass(c, "p", _body(proof="Step 1: the pair exists."),
                          {"verdict": "pass"}, [], 0, "batch-1")
    g1 = _authorised_goal(c, slug="early", batch_id="batch-1",
                          decision_id=None)
    programme.record_pass(c, "p", _body(proof="Step 9: unrelated."),
                          {"verdict": "pass"}, [], 0, "batch-2")
    g2 = _authorised_goal(c, slug="late", batch_id="batch-2",
                          decision_id=None)

    assert programme.current_rev(c, "p")["rev"] == 2
    assert programme.rev_for_goal(c, "p", goal_id=g1)["rev"] == 1
    assert programme.rev_for_goal(c, "p", goal_id=g2)["rev"] == 2
    assert "Step 1" in programme.rev_for_goal(c, "p", goal_id=g1)["body"]


def test_rev_for_goal_inherits_through_worker_created_subgoals(tmp_path):
    """A sub-goal the worker decomposed out has no decision of its own —
    it was authorised by the same argument as its parent. Without the
    upward walk this is exactly the case that silently re-anchors: the
    dispatcher relays sub-goals with no Strategist wake at all."""
    c = _fresh(tmp_path)
    programme.record_pass(c, "p", _body(proof="Step 1: the pair exists."),
                          {"verdict": "pass"}, [], 0, "batch-1")
    parent = _authorised_goal(c, slug="parent", batch_id="batch-1",
                              decision_id=None)
    sid = db.insert_strategy(c, goal_id=parent,
                             lean_path="Problems/p/proofs/L_parent.lean",
                             scratch_path="Problems/p/proofs/_s.lean",
                             proposal_md="-- split", created_by="pipe-1")
    kid = db.insert_goal(c, problem="p", slug="kid",
                         lean_path="Problems/p/proofs/L_kid.lean",
                         statement="theorem kid : T", origin="backward",
                         depth=2, status="open")
    c.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
              " position) VALUES (?, ?, 0)", (sid, kid))
    c.commit()
    programme.record_pass(c, "p", _body(proof="Step 9: unrelated."),
                          {"verdict": "pass"}, [], 0, "batch-2")

    assert programme.current_rev(c, "p")["rev"] == 2
    assert programme.rev_for_goal(c, "p", goal_id=kid)["rev"] == 1


def test_rev_for_goal_prefers_the_dispatching_decision(tmp_path):
    """A re-Inject on an existing goal is a NEW authorisation. The spawn
    it dispatched must read the rev that dispatched IT, which is why
    `decision_id` outranks the goal's own provenance."""
    c = _fresh(tmp_path)
    programme.record_pass(c, "p", _body(proof="Step 1."),
                          {"verdict": "pass"}, [], 0, "batch-1")
    g = _authorised_goal(c, slug="revisited", batch_id="batch-1",
                         decision_id=None)
    programme.record_pass(c, "p", _body(proof="Step 2, reframed."),
                          {"verdict": "pass"}, [], 0, "batch-2")
    c.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, target_id, created_at,"
        " updated_at) VALUES ('p', 0, 'routine', 'Inject', 'batch-2', ?,"
        " ?, ?)", (g, db.now(), db.now()))
    did = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    c.commit()

    assert programme.rev_for_goal(c, "p", goal_id=g)["rev"] == 1
    assert programme.rev_for_goal(c, "p", goal_id=g,
                                  decision_id=did)["rev"] == 2


def test_rev_for_goal_falls_back_to_current(tmp_path):
    """Nothing above has an authorisation — a fresh problem, or work
    predating the Programme. Fall back rather than render nothing: the
    worker premise section must not vanish."""
    c = _fresh(tmp_path)
    programme.record_pass(c, "p", _body(), {"verdict": "pass"}, [], 0,
                          "batch-1")
    orphan = db.insert_goal(c, problem="p", slug="orphan",
                            lean_path="Problems/p/proofs/L_orphan.lean",
                            statement="theorem orphan : T",
                            origin="forward", depth=1, status="open")
    c.commit()
    assert programme.rev_for_goal(c, "p", goal_id=orphan)["rev"] == 1
    assert programme.rev_for_goal(c, "p")["rev"] == 1


def test_rev_for_goal_takes_the_latest_authorisation_at_the_same_depth(
    tmp_path,
):
    """A goal re-Injected later carries two producing decisions. The
    live one is the latest — an older row must not drag the worker back
    to a superseded argument, which is the one way this walk can be
    WRONG rather than merely unhelpful (the cascade's other failure mode
    is falling back to current_rev, i.e. the old behaviour)."""
    c = _fresh(tmp_path)
    programme.record_pass(c, "p", _body(proof="Step 1, first pass."),
                          {"verdict": "pass"}, [], 0, "batch-1")
    g = _authorised_goal(c, slug="twice", batch_id="batch-1",
                         decision_id=None)
    programme.record_pass(c, "p", _body(proof="Step 1, reframed."),
                          {"verdict": "pass"}, [], 0, "batch-2")
    # Re-Inject on the same goal: `produced_goal_id` is set again
    # (produced_kind='redispatch'), so both rows sit at depth 0.
    c.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, target_id,"
        " produced_goal_id, created_at, updated_at)"
        " VALUES ('p', 0, 'routine', 'Inject', 'batch-2', ?, ?, ?, ?)",
        (g, g, db.now(), db.now()))
    c.commit()

    row = programme.rev_for_goal(c, "p", goal_id=g)
    assert row["rev"] == 2
    assert "reframed" in row["body"]
