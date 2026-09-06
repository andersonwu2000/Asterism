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
    c.execute("INSERT INTO problems (name, created_at,"
              " bootstrap_done) VALUES ('p',?,1)", (db.now(),))
    c.commit()
    return c


def _body(proof=("### close_gcd\n"
                 "Theorem. The gcd gap closes.\n"
                 "Proof. The route holds because of X."),
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
    assert sections["proof"].startswith("### close_gcd")


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


def test_summary_section_is_not_a_field_and_the_column_stays_null(tmp_path):
    """Owner ruling 2026-09-02: no `## Summary` on a proposal — the
    Programme is already prose a mathematician reads. The v48 column
    survives (dropping it is a table rebuild for nothing) and stays
    NULL: nothing parses, derives or writes it."""
    c = _fresh(tmp_path)
    body = _body() + "## Summary\nA paragraph nobody asked for.\n"
    sections, err = programme.parse_proposal(body)
    assert err is None and "summary" not in sections
    programme.record_pass(c, "p", body, {"verdict": "pass"}, [], 1, "b1")
    assert c.execute(
        "SELECT summary FROM programme_revisions").fetchone()[0] is None


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

    # Roadmap-specific warn (2026-08-04, SLC growth curve: ~600B/rev
    # with closed arcs still itemized) — fires below the blunt
    # whole-document threshold.
    body = _body(roadmap="r" * (programme.ROADMAP_WARN_CHARS + 1))
    long_rm, _ = programme.parse_proposal(body)
    warn = programme.length_warning(long_rm, body)
    assert warn and "ROADMAP LENGTH WARNING" in warn
    assert "PROPOSAL LENGTH" not in warn and "PROOF LENGTH" not in warn

    # Conventions warn (2026-08-04): the section rides EVERY worker
    # spawn, so its threshold is the tightest of the four.
    body = (_body() + "## Conventions\n"
            + "c" * (programme.CONVENTIONS_WARN_CHARS + 1) + "\n")
    long_cv, err = programme.parse_proposal(body)
    assert err is None
    warn = programme.length_warning(long_cv, body)
    assert warn and "CONVENTIONS LENGTH WARNING" in warn
    assert "ROADMAP LENGTH" not in warn

    body = _body(roadmap="r" * (programme.DOC_WARN_CHARS + 1))
    long_doc, _ = programme.parse_proposal(body)
    warn = programme.length_warning(long_doc, body)
    assert warn and "PROPOSAL LENGTH WARNING" in warn


def test_native_decide_route_warns_the_judge():
    """Owner call 2026-08-25: union_closed shipped TEN passed revisions
    planning `native_decide` routes; every brick died at the commit
    axiom gate, and only the dying worker saw the gate's teaching — the
    NL layer kept re-planning.

    2026-09-04 requirement change: the notice is its OWN function, not
    a length warning — the two ride different surfaces (the judge reads
    both; only the length one carries "come back smaller"). And the
    wording is QUALIFIED: the mention alone proves nothing, a closure
    note or a prohibition mentions the token too."""
    body = _body(proof="the filter is empty by native_decide")
    warn = programme.native_decide_warning(body)
    assert warn and "NATIVE_DECIDE NOTICE" in warn
    assert "ofReduceBool" in warn
    # The claim is conditional, not "the batch cannot land".
    assert "If a planned brick's formalization must use it" in warn
    # `Lean.ofReduceBool` on its own trips it too (rpc.py's regex).
    assert programme.native_decide_warning(
        _body(proof="the axiom Lean.ofReduceBool")) is not None
    # …but a word merely containing the token does not.
    assert programme.native_decide_warning(
        _body(proof="see nonnative_decideish notes")) is None
    # The length surface no longer carries it (requirement change).
    sections, _ = programme.parse_proposal(body)
    assert programme.length_warning(sections, body) is None
    # clean proposals stay warning-free
    ok, _ = programme.parse_proposal(_body())
    assert programme.length_warning(ok) is None
    assert programme.native_decide_warning(_body()) is None


def test_native_decide_confirm_asks_once_per_wake():
    """The soft confirm gate (owner design 2026-09-04, the shape the
    formalizer side already has in `rpc.py::_native_decide_gate`): the
    first proposal mentioning the token is bounced back to the author
    unjudged, and the resubmission — revised OR unchanged — goes to the
    judge. Asked once per wake, never twice."""
    body = _body(proof="close it by native_decide")
    ask = programme.native_decide_confirm(body, asked=False)
    assert ask and "NATIVE_DECIDE NOTICE" in ask
    assert "Resubmit proposal.md" in ask
    # Already asked this wake → silent, whatever the body says.
    assert programme.native_decide_confirm(body, asked=True) is None
    # No mention → nothing to confirm.
    assert programme.native_decide_confirm(_body(), asked=False) is None


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


def test_rev_for_goal_decision_fallback_stays_in_the_decisions_group(
        tmp_path):
    """#164 class: v35 chains are per group. A decision whose batch has
    no passed rev yet must fall back to ITS group's current rev — the
    problem-wide max is a SIBLING group's argument (top chain at rev 2
    here, so the old fallback would hand the child's mint 'Top step 2')."""
    from Tooling.state import groups as groups_store
    c = _fresh(tmp_path)
    top = groups_store.ensure_top_group(c, "p")
    programme.record_pass(c, "p", _body(proof="Top step 1."),
                          {"verdict": "pass"}, [], 0, "t1", group_id=top)
    programme.record_pass(c, "p", _body(proof="Top step 2."),
                          {"verdict": "pass"}, [], 0, "t2", group_id=top)
    child = groups_store.open_group(c, problem="p", parent_group_id=top,
                                    charter="settle the sub-claim")
    programme.record_pass(c, "p", _body(proof="Child step."),
                          {"verdict": "pass"}, [], 0, "c1", group_id=child)
    # An infra-retry shape: the child's decision rides a batch id with
    # no programme_revisions row, so resolution paths 1-2 both miss.
    c.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, batch_id, group_id, created_at,"
        " updated_at) VALUES ('p', 0, 'routine', 'Inject',"
        " 'unreviewed-batch', ?, ?, ?)", (child, db.now(), db.now()))
    did = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
    c.commit()

    row = programme.rev_for_goal(c, "p", decision_id=did)
    assert "Child step." in row["body"]


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


# ------------------------------------------- Roadmap citation rejection

def test_roadmap_tag_content_is_never_string_matched(tmp_path):
    """The `Roadmap:` line's CONTENT is a semantic citation the
    Adversary judges — the verifier must not test it against the
    free-prose Roadmap. The old plain-substring gate was free-text
    detection (forbidden by the design rules) and bounced whole
    batches five times over phrasing (2026-08-03 feedback #4,
    operator ruling: the Roadmap stays pure NL)."""
    from types import SimpleNamespace
    from Tooling.pipeline import strategist
    roadmap = "**Dispatched this batch: the root Inject.**"
    (tmp_path / "proposal.md").write_text(
        _body(roadmap=roadmap), encoding="utf-8")
    d = SimpleNamespace(kind="Inject", target_id=None,
                        brief="Roadmap: Genus-1 model — Brick 1, "
                              "the gluing word\n## Need\nx")
    _b, _s, _br, err = strategist.verify_proposal_package([d], tmp_path)
    assert err is None, f"phrase mismatch must not bounce a batch: {err}"


def test_the_roadmap_tag_line_is_no_longer_required(tmp_path):
    """Retired 2026-08-11. "Some line begins `Roadmap:`" was satisfied by
    `Roadmap: x`: it could not fail a batch that was wrong, and it could
    still fail one that was right, while being the last mechanical
    reader of a field the Strategist writes as prose. The correspondence
    it stood in for is the Adversary's, under criteria 1/4 — where the
    2026-08-03 ruling ("the Roadmap stays pure NL") already put the
    content half of the same question."""
    from types import SimpleNamespace
    from Tooling.pipeline import strategist
    (tmp_path / "proposal.md").write_text(_body(), encoding="utf-8")
    d = SimpleNamespace(kind="Inject", target_id=None,
                        brief="## Need\nx")
    _b, _s, _br, err = strategist.verify_proposal_package([d], tmp_path)
    assert err is None


# --------------------------------------------- Conventions (RS-B, 08-03)

def test_conventions_section_is_optional_and_parsed(tmp_path):
    """`## Conventions` is the retired EmitDirective's successor: optional,
    after `## Roadmap`, may be empty-absent but not misplaced."""
    body = _body() + "## Conventions\n- cite by CATALOG name\n- no nested namespace\n"
    sections, err = programme.parse_proposal(body)
    assert err is None
    assert "cite by CATALOG name" in sections["conventions"]
    # absent → empty string, not an error
    sections2, err2 = programme.parse_proposal(_body())
    assert err2 is None and sections2["conventions"] == ""
    # misplaced (before Roadmap) → teaching rejection
    bad = ("# T\n## Argument\na\n## Proof\np\n"
           "## Conventions\nc\n## Roadmap\nr\n")
    _s, err3 = programme.parse_proposal(bad)
    assert err3 and "after `## Roadmap`" in err3


def test_conventions_for_group_never_walks_the_ancestor_chain(tmp_path):
    """A group's workers see that group's conventions and nothing above
    (2026-08-11, owner call). The chain shipped a sibling line's working
    vocabulary to every spawn — 3,088 B of graph rules for a brick with
    no graph. A parent that needs a rule down there writes it down."""
    c = _fresh(tmp_path)
    from Tooling.state import groups
    top = groups.ensure_top_group(c, "p")
    kid = groups.open_group(c, problem="p", parent_group_id=top,
                            charter="settle the lemma")
    programme.record_pass(
        c, "p", _body() + "## Conventions\nTOP RULE\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=top)
    programme.record_pass(
        c, "p", _body() + "## Conventions\nKID RULE\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=kid)
    text = programme.conventions_for_group(c, "p", kid)
    assert "KID RULE" in text
    assert "TOP RULE" not in text
    assert "KID RULE" not in programme.conventions_for_group(c, "p", top)


def test_conventions_seed_carries_until_the_group_writes_its_own(tmp_path):
    """Copy-on-open: the footgun a parent already knows reaches a group
    opened later, because that group could never ask for a rule it does
    not know exists. It stops being read the moment the group ships its
    own section — including when the group deliberately drops it."""
    c = _fresh(tmp_path)
    from Tooling.state import groups
    top = groups.ensure_top_group(c, "p")
    programme.record_pass(
        c, "p", _body() + "## Conventions\nVERIFY NAMES AGAINST CATALOG\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=top)
    kid = groups.open_group(
        c, problem="p", parent_group_id=top, charter="settle the lemma",
        conventions_seed=programme.conventions_for_group(c, "p", top))
    # Before its first revision the child runs on the seed.
    assert "VERIFY NAMES" in programme.conventions_for_group(c, "p", kid)
    # Its own section supersedes it — wholly, drops included.
    programme.record_pass(
        c, "p", _body() + "## Conventions\nKID RULE ONLY\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=kid)
    text = programme.conventions_for_group(c, "p", kid)
    assert text == "KID RULE ONLY"


def test_conventions_seed_is_a_snapshot_not_a_link(tmp_path):
    """The seed is copied at open time. A parent revising afterwards does
    not reach back into a child already running — that is the whole
    difference between copy-on-open and the chain walk it replaced."""
    c = _fresh(tmp_path)
    from Tooling.state import groups
    top = groups.ensure_top_group(c, "p")
    programme.record_pass(
        c, "p", _body() + "## Conventions\nRULE AT OPEN TIME\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=top)
    kid = groups.open_group(
        c, problem="p", parent_group_id=top, charter="settle the lemma",
        conventions_seed=programme.conventions_for_group(c, "p", top))
    programme.record_pass(
        c, "p", _body() + "## Conventions\nRULE ADDED LATER\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=top)
    text = programme.conventions_for_group(c, "p", kid)
    assert "RULE AT OPEN TIME" in text
    assert "RULE ADDED LATER" not in text


def test_emit_directive_is_retired(tmp_path):
    """New EmitDirective decisions are rejected with a teaching message
    pointing at the Conventions section; the DB CHECK keeps the value
    for historical rows (v35 lesson — never strand old data)."""
    from types import SimpleNamespace
    from Tooling.pipeline.strategist import verify_decision
    c = _fresh(tmp_path)
    d = SimpleNamespace(kind="EmitDirective", target_id=None, brief=None,
                        reason="r", payload={"scope": "problem:p",
                                             "body": "do X"})
    err = verify_decision(d, c, problem="p")
    assert "retired" in err and "## Conventions" in err


# ---------------------------------------------------------------------
# The discard-channel split (v37, 2026-08-08)
# ---------------------------------------------------------------------

def _discard(c, channel, *, rounds=8):
    programme.record_rejection(
        c, "p", _body(proof="The load-bearing step."),
        [{"round": 1, "role": "adversary",
          "criticisms": ["[criterion 3] step 2 assumes t-s > 0"],
          "proposal": "older body"},
         {"round": 2, "role": "adversary",
          "criticisms": ["[criterion 1] distance to MAIN unchanged"],
          "proposal": "newer body"}],
        rounds, discard_reason="whatever prose", group_id=None,
        discard_channel=channel)


def test_adversary_exhaustion_still_withholds_the_draft(tmp_path):
    """The ratified destructive semantics (design §1/§3): a refuted
    proposal is NOT shown to the next session — it must re-derive with
    fresh eyes rather than defend a body the judge already broke."""
    c = _fresh(tmp_path)
    _discard(c, "strategist_proposal_rejected")
    notice = programme.rejection_notice(c, "p")
    assert notice.endswith("draft not shown.")
    assert "load-bearing step" not in notice
    assert "criterion 3" not in notice


def test_infra_discard_hands_the_draft_over(tmp_path):
    """An infra death refuted nothing, so the anti-anchoring rationale
    does not apply: withholding just burns the rounds again (2026-08-07,
    an 8-round debate re-derived from one line because a subscription
    window expired mid-revision)."""
    c = _fresh(tmp_path)
    _discard(c, "quota_exhausted")
    notice = programme.rejection_notice(c, "p")
    assert "draft not shown" not in notice
    assert "The load-bearing step." in notice          # the body
    assert "criterion 3" in notice and "criterion 1" in notice
    assert "Round 1 criticisms" in notice              # oldest first
    assert notice.index("Round 1") < notice.index("Round 2")
    assert "the machine failed, not the argument" in notice


def test_legacy_null_channel_reads_as_adversarial(tmp_path):
    """Pre-v37 rows have no channel and every one of them came from the
    Adversary — defaulting them to "show the draft" would retroactively
    break the ratified blindness."""
    c = _fresh(tmp_path)
    programme.record_rejection(c, "p", _body(), [], 3)
    assert programme.rejection_notice(c, "p").endswith("draft not shown.")


def test_infra_channels_are_registry_reasons(tmp_path):
    """The gate reads a structured signal, and every value in it must be
    a real registry failure_reason — a typo would silently downgrade an
    infra death to the blind path (the quota-ledger disease, 08-07)."""
    from Tooling.state import failures
    unknown = programme._INFRA_DISCARD_CHANNELS - set(failures.REGISTRY)
    assert not unknown, unknown
    # And every provider-infra reason must be on the show-the-draft
    # side: none of them is an argument the judge refuted.
    assert failures.PROVIDER_INFRA_REASONS <= programme._INFRA_DISCARD_CHANNELS


# ---------------------------------------------- the discarded cycle's rebuttals

def test_rejection_cycle_is_the_consecutive_discards_since_the_last_pass(tmp_path):
    """The successor of a discarded cycle needs the judge's rebuttals of
    THAT cycle — every rejected rev since the last pass, oldest first —
    and, of the latest one, the round that killed it. 2026-08-30: a
    successor that saw one line ('draft not shown') and its own plan
    note re-argued the refuted route for five more rounds."""
    c = _fresh(tmp_path)
    programme.record_pass(c, "p", _body(proof="Pass 1."),
                          {"verdict": "pass"}, [], 0, "b1")
    programme.record_rejection(
        c, "p", _body(proof="Dead draft A."),
        [{"round": 1, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 1] A dies"]}],
        1, discard_reason="adversary rebuttal",
        discard_channel="strategist_proposal_rejected")
    programme.record_rejection(
        c, "p", _body(proof="Dead draft B."),
        [{"round": 1, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 2] B dies"]},
         {"round": 2, "role": "adversary", "verdict": "rebut",
          "criticisms": ["[criterion 1] B still dies"]}],
        2, discard_reason="adversary rebuttal",
        discard_channel="strategist_proposal_rejected")
    c.commit()
    cyc = programme.rejection_cycle(c, "p")
    # rejected rows do not consume a rev number (both sit at 'rev 2');
    # the cycle is ordered by id, oldest first
    assert len(cyc) == 2, "both discards"
    assert "Dead draft A." in cyc[0]["body"] and "Dead draft B." in cyc[1]["body"], "oldest first"
    rnd, crits = programme.last_rebuttal(cyc[-1])
    assert rnd == 2 and crits == ["[criterion 1] B still dies"]
    programme.record_pass(c, "p", _body(proof="Pass 2."),
                          {"verdict": "pass"}, [], 0, "b2")
    c.commit()
    assert programme.rejection_cycle(c, "p") == [], "a pass closes the cycle"
