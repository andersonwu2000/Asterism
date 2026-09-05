"""The Theorist pipeline (theory_wake_design.md §3): author, review,
land — and what happens on every road that is not "accepted".

Mocked `spawn_llm`, everything else real: the Context is compiled from
a live DB, the projection is assembled on disk, the verdict goes
through the real parser and an accepted document lands through the real
`_docs` write fence.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from Tooling import agent
from Tooling.pipeline import theorist
from Tooling.pipeline.strategist import commit as _commit
from Tooling.pipeline.theorist import landing, verdict as _verdict
from Tooling.state import db, groups as groups_mod, intent


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(
        json.dumps({"problem": "p", "charter": "Statement: T"}),
        encoding="utf-8")
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    groups_mod.ensure_top_group(c, "p", charter="T")
    c.commit()
    return c


@pytest.fixture
def pintent() -> intent.ProblemIntent:
    return intent.ProblemIntent(problem="p", charter="T")


_REPORT = ("# The unit-imbalance erasure\n\n"
           "## Abstract\n\nIt reduces MAIN to a smaller claim.\n\n"
           "## Theorems and proofs\n\nTheorem 1. ...\n\n"
           "## Load-bearing work\n\nThe wall is X.\n\n"
           "## Leads\n\nConjecture A, tested on n=4.\n")


def _clear(**over):
    base = {k: [f"clear: criterion {k} holds because ..."]
            for k in _verdict.CRITERIA_KEYS}
    base.update(over)
    return {"criteria": base, "reservations": []}


def _fired(key: str = "1", text: str = "the relation is not argued"):
    return _clear(**{key: [f"fired: {text}"]})


def _theorize(conn: sqlite3.Connection, workspace: Path, *,
              objective: str = "S such that S implies MAIN",
              situation: str = "the bridge died at PAST 3",
              actor: str = _commit.ACTOR_STRATEGIST) -> int:
    """File a real `Theorize` and hand back its decision row id."""
    from Tooling.pipeline.strategist import parse_decision
    d, err = parse_decision(json.dumps(
        {"kind": "Theorize", "objective": objective,
         "situation": situation}))
    assert err == "", err
    gid = groups_mod.ensure_top_group(conn, "p")
    out = _commit.commit_decisions(
        [d], conn, problem="p", tick=0, trigger_kind="routine",
        workspace=workspace, group_id=gid, actor=actor)[0]
    return int(out.decision_row_id)


def _script(*, verdicts, report=_REPORT):
    """A scripted `spawn_llm`: the author writes `report.md` every turn,
    the reviewer writes the next verdict in the list."""
    state = {"author": 0, "review": 0, "author_sids": [],
             "review_sids": [], "rebuttals": [], "seats": []}

    def fake_spawn(**kw):
        kind = kw.get("kind")
        state["seats"].append(kind)
        if kind == "theory_reviewer":
            state["review"] += 1
            state["review_sids"].append(kw.get("session_id"))
            v = verdicts[min(state["review"] - 1, len(verdicts) - 1)]
            if v is not None:
                (kw["attempts_dir"] / "verdict.json").write_text(
                    json.dumps(v), encoding="utf-8")
            return 0
        state["author"] += 1
        state["author_sids"].append(kw.get("session_id"))
        state["rebuttals"].append(kw.get("retry_context"))
        body = report if isinstance(report, str) else report(state["author"])
        if body is not None:
            (kw["attempts_dir"] / "report.md").write_text(
                body, encoding="utf-8")
        return 0

    return fake_spawn, state


def _run(conn, workspace, pintent, decision_id, pipeline_id="th-1"):
    return theorist.run_theorist(
        conn, problem="p", workspace=workspace, intent=pintent,
        pipeline_id=pipeline_id,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        decision_id=decision_id)


# ---------------------------------------------------------------------
# the accepted road
# ---------------------------------------------------------------------

def test_an_accepted_document_lands_and_settles_its_request(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One author turn, one clear verdict: the document lands under the
    Project's shelf, `theory_documents` records it, and the Theorize row
    settles with the PATH — which is what the next wake reads."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success", r.failure_detail
    assert state["author"] == 1 and state["review"] == 1
    assert state["seats"] == ["theorist", "theory_reviewer"]

    row = conn.execute(
        "SELECT path, status, rounds, group_id, decision_id,"
        " objective, verdict_json FROM theory_documents").fetchone()
    assert row["status"] == "accepted" and row["rounds"] == 1
    assert row["decision_id"] == did
    assert row["objective"] == "S such that S implies MAIN"
    landed = workspace / row["path"]
    assert landed.is_file()
    text = landed.read_text(encoding="utf-8")
    # The provenance the attempts dir cannot keep: it is deleted at
    # pipeline end, so the reviewer's per-criterion sentence lives here.
    assert text.startswith("<!--")
    assert "pipeline: th-1" in text and "rounds: 1" in text
    for k in _verdict.CRITERIA_KEYS:
        assert f"criterion {k}: clear:" in text
    assert "# The unit-imbalance erasure" in text
    assert "_docs/agent/" in row["path"]

    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert d["outcome"] == "success"
    assert d["outcome_detail"] == row["path"]


def test_the_landed_name_carries_group_minute_and_title(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`g<group>_<YYYYMMDD-HHMM>_<slug>.md`: the group and the minute
    make two documents on one wall tellable apart in a flat listing,
    the slug makes either of them findable."""
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    name = Path(conn.execute(
        "SELECT path FROM theory_documents").fetchone()[0]).name
    assert name.startswith(f"g{gid}_")
    assert name.endswith("_the_unit_imbalance_erasure.md")


def test_the_slug_falls_back_to_the_abstracts_first_sentence(
) -> None:
    """A document with no `# ` line is still findable: the Abstract's
    first sentence is where this structure puts the claim."""
    assert landing.slug_for("# A Title Here\n\nx") == "a_title_here"
    assert landing.slug_for(
        "## Abstract\n\nIt reduces MAIN to a smaller claim. And more.\n"
    ) == "it_reduces_main_to_a_smaller_claim"
    assert landing.slug_for("no headings at all") == "untitled"


# ---------------------------------------------------------------------
# the review loop
# ---------------------------------------------------------------------

def test_a_fired_verdict_buys_a_revision_on_the_same_session(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fired bullets go back VERBATIM, on a resume of the author's
    own session — the exact path the batch wake's rebuttal rides — and
    the reviewer is fresh every round."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_fired("3", "the wall is only named"),
                                    _clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "success"
    assert state["author"] == 2 and state["review"] == 2
    assert len(set(state["author_sids"])) == 1
    assert len(set(state["review_sids"])) == 2
    assert state["rebuttals"][0] is None
    assert "[criterion 3] the wall is only named" in state["rebuttals"][1]
    assert conn.execute(
        "SELECT rounds FROM theory_documents").fetchone()[0] == 2
    # the earlier round's objection reaches the reviewer as dialogue
    dialogue = (workspace / ".attempts" / "th-1" / "review" / "r2"
                / "dialogue.md")
    assert dialogue.is_file()
    assert "the wall is only named" in dialogue.read_text(encoding="utf-8")


def test_three_fired_rounds_reject_and_the_document_does_not_land(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four author turns (one cold + three revisions), then the run is
    over. Nothing reaches the Project's shelf — it did not earn a place
    there — and the row that survives carries the request, the rounds
    and the last verdict, which is what the next request is written
    against."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[_fired("1"), _fired("1"),
                                    _fired("1"), _fired("1")])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert r.failure_reason == "theory_rejected"
    assert state["author"] == 4 and state["review"] == 4

    row = conn.execute(
        "SELECT path, status, rounds, verdict_json FROM theory_documents"
    ).fetchone()
    assert row["status"] == "rejected" and row["path"] is None
    assert row["rounds"] == 4
    assert "the relation is not argued" in row["verdict_json"]
    assert not list((workspace / "Problems" / "p" / "_docs" / "agent"
                     ).glob("*")) if (
        workspace / "Problems" / "p" / "_docs" / "agent").is_dir() else True

    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    # The one road REJECTED_DETAIL is for: a ruling was made and it
    # fired. Named on the enum too, so no consumer has to read prose.
    assert str(d["outcome"]) == "failed:theory_rejected"
    assert theorist.REJECTED_DETAIL in d["outcome_detail"]
    assert "the relation is not argued" in d["outcome_detail"]


def test_a_settled_request_wakes_the_group(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of settling the row: the batch closes, so the
    group is woken with the answer instead of waiting on a request that
    already finished."""
    gid = groups_mod.ensure_top_group(conn, "p")
    did = _theorize(conn, workspace)
    assert not db.is_in_queue(conn, target_id=str(gid), kind="Strategist")
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    assert db.is_in_queue(conn, target_id=str(gid), kind="Strategist")


# ---------------------------------------------------------------------
# a spawn that died is not a review that refused
# ---------------------------------------------------------------------

def _dead_spawn(seat: str, *, rc: int = 1, report: "str | None" = None):
    """A scripted `spawn_llm` where `seat` exits `rc`. The author writes
    `report` first when one is given; every other seat behaves."""
    state = {"author": 0, "review": 0}

    def fake_spawn(**kw):
        kind = kw.get("kind")
        if kind == "theory_reviewer":
            state["review"] += 1
            if seat == kind:
                return rc
            (kw["attempts_dir"] / "verdict.json").write_text(
                json.dumps(_clear()), encoding="utf-8")
            return 0
        state["author"] += 1
        if report is not None:
            (kw["attempts_dir"] / "report.md").write_text(
                report, encoding="utf-8")
        return rc if seat == kind else 0

    return fake_spawn, state


def test_a_dead_author_spawn_is_not_reported_as_a_rejection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-09-05, union_closed g691 twice: the codex stream died on the
    author's idle timeout and the Strategist was told its request "did
    not pass review — reconsider your request". Nothing was reviewed.
    A transport death must name the reachable action instead, and the
    decision's own `outcome` must say which road it was, so a reader
    does not have to parse prose to tell them apart."""
    did = _theorize(conn, workspace)
    fake, state = _dead_spawn("theorist")
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert state["review"] == 0       # nothing was reviewed
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert "did not complete" in d["outcome_detail"]
    assert "re-issue" in d["outcome_detail"]
    # structural, not textual: `failed:<reason>`, the vocabulary
    # `failed:dead` / `failed:stalled` / `failed:group_retired` use.
    assert str(d["outcome"]) == f"failed:{r.failure_reason}"


def test_a_dead_reviewer_spawn_is_not_reported_as_a_rejection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reviewer's transport can die on the same wall as the
    author's, and its rc says nothing about the document either."""
    did = _theorize(conn, workspace)
    fake, _ = _dead_spawn("theory_reviewer", report=_REPORT)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert "did not complete" in d["outcome_detail"]
    assert str(d["outcome"]) == f"failed:{r.failure_reason}"


def test_an_author_that_writes_nothing_is_a_dead_wake_not_a_rejection(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No document was ever put to the reviewer, so no reviewer refused
    it — the same road, reached without an rc."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()], report=lambda _n: None)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    d = conn.execute(
        "SELECT outcome, outcome_detail FROM strategist_decisions"
        " WHERE id = ?", (did,)).fetchone()
    assert theorist.REJECTED_DETAIL not in d["outcome_detail"]
    assert str(d["outcome"]) == "failed:theory_no_report"


# ---------------------------------------------------------------------
# the roads that are not a verdict
# ---------------------------------------------------------------------

def test_an_author_that_writes_nothing_settles_the_request_anyway(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NULL outcome means "the theory layer is still working"
    everywhere in the framework, so a pipeline that returned without
    writing one would suppress its group's stall rescue forever."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()], report=lambda _n: None)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed" and r.failure_reason == "theory_no_report"
    d = conn.execute("SELECT outcome FROM strategist_decisions"
                     " WHERE id = ?", (did,)).fetchone()
    assert d["outcome"] is not None
    assert not db.has_active_inflight_inject(
        conn, "p", group_id=groups_mod.ensure_top_group(conn, "p"))


def test_a_reviewer_that_never_produces_a_verdict_costs_two_tries(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One malformed file must not cost the author's document, and a
    reviewer that produced no usable ruling twice is a pipeline-level
    failure."""
    did = _theorize(conn, workspace)
    fake, state = _script(verdicts=[None])
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = _run(conn, workspace, pintent, did)
    assert r.outcome == "failed"
    assert r.failure_reason == "theory_no_verdict"
    assert state["review"] == _verdict.VERDICT_TRIES
    assert state["author"] == 1


def test_a_refused_verdict_is_kept_beside_the_one_that_replaces_it(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused verdict IS the evidence for its refusal: it moves
    aside, it does not vanish, and the second refusal in one round does
    not overwrite the first."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[{"criteria": {"1": ["clear"]}},
                                {"criteria": {"1": ["clear"]}}])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)
    proj = workspace / ".attempts" / "th-1" / "review" / "r1"
    kept = sorted(p.name for p in proj.glob("verdict_r1_raw*.json"))
    assert kept == ["verdict_r1_raw.json", "verdict_r1_raw2.json"]
    assert not (proj / "verdict.json").exists()


# ---------------------------------------------------------------------
# the reviewer's dossier
# ---------------------------------------------------------------------

def test_the_projection_carries_the_request_and_declares_its_rubric(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`request.md` is its own file — criterion 1 asks whether the
    document answers THIS request, and a request the author could have
    edited on the way past is not a thing to judge against.
    `_verdict_rubric.json` is what stops `validate_json` telling a
    complete four-criterion verdict it is missing criterion 5."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    proj = workspace / ".attempts" / "th-1" / "review" / "r1"
    req = (proj / "request.md").read_text(encoding="utf-8")
    assert "S such that S implies MAIN" in req
    assert "the bridge died at PAST 3" in req
    rubric = json.loads((proj / "_verdict_rubric.json").read_text(
        encoding="utf-8"))
    assert rubric["criteria_keys"] == list(_verdict.CRITERIA_KEYS)
    assert rubric["multi_clear"] is True
    assert (proj / "report.md").read_text(encoding="utf-8").startswith(
        "# The unit-imbalance erasure")
    assert (proj / "PROGRAMME.md").is_file()
    assert (proj / "TREE.md").is_file()


def test_the_author_reads_its_group_under_the_theory_trigger(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Context is the group's own, compiled for `theory`: the
    request leads it, and the Programme is a POINTER — the author reads
    the revision where it bears on the wall rather than paying for all
    of it inline."""
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    ctx = (workspace / ".attempts" / "th-1" / "Context.md"
           ).read_text(encoding="utf-8")
    assert "`trigger_kind`: theory" in ctx
    assert "### Objective" in ctx and "### Situation" in ctx
    assert "S such that S implies MAIN" in ctx
    assert "## Programme" in ctx
    assert "`PROGRAMME.md` beside this file" in ctx
    assert (workspace / ".attempts" / "th-1" / "PROGRAMME.md").is_file()


# ---------------------------------------------------------------------
# the verdict parser's own contract
# ---------------------------------------------------------------------

def test_several_clears_in_one_criterion_are_legal() -> None:
    """A theory document carries several theorems and several leads, so
    a criterion that asks about them is answered one bullet per item.
    The batch judge's "clear takes exactly one entry" ended BOTH arm5F
    runs as `judge_no_verdict` on verdicts that were entirely clear."""
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"4": ["clear: lead A survived n=4",
                 "clear: lead B survived the construction"]})))
    assert err == "" and v is not None
    assert v["verdict"] == "pass"


def test_a_bare_clear_is_refused_in_every_rendering() -> None:
    """Per BULLET, so a bare one cannot hide behind a reasoned
    neighbour — and an object whose prose is empty is the same bare
    word wearing a different shape."""
    for bad in (["clear"],
                ["clear: good reason", "clear"],
                [{"verdict": "clear"}]):
        v, err = _verdict.parse_theory_verdict(
            json.dumps(_clear(**{"2": bad})))
        assert v is None and "bare" in err, bad


def test_a_criterion_is_one_ruling() -> None:
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"2": ["clear: it holds", "fired: except here"]})))
    assert v is None and "mixes" in err


def test_a_missing_criterion_names_the_one_that_is_missing() -> None:
    body = _clear()
    body["criteria"].pop("3")
    v, err = _verdict.parse_theory_verdict(json.dumps(body))
    assert v is None and "criterion 3" in err
    assert "5" not in err


def test_a_bullet_rendered_as_an_object_is_still_a_bullet() -> None:
    """Refusing this rendering cost arm3h_r2 both of its tries: the
    contract is one bullet per objection, and the bullet's SHAPE is not
    the contract."""
    v, err = _verdict.parse_theory_verdict(json.dumps(_clear(
        **{"1": [{"verdict": "fired", "reason": "already in the notes"}]})))
    assert err == "" and v is not None
    assert v["verdict"] == "rebut"
    assert v["criticisms"] == ["[criterion 1] already in the notes"]


# ---------------------------------------------------------------------
# the surfaces that read a decision, a pipeline or a table
# ---------------------------------------------------------------------

def _batch_section(conn, workspace, attempts):
    from Tooling.agent import phase2_context
    return phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts)


def _open_theorize(conn, workspace):
    """One open Theorize plus the pipeline row its dispatch would make."""
    did = _theorize(conn, workspace)
    db.record_pipeline_start(
        conn, pipeline_id="pid-th", kind="Theorist",
        target_id=str(groups_mod.ensure_top_group(conn, "p")),
        target_kind="Group")
    return did


def test_the_status_surfaces_read_a_theory_run_without_crashing(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A new pipeline kind and a new decision kind reach every reader of
    those tables. None of them may die on it — a status command that
    raises is the operator's only window going dark at exactly the
    moment something new is running."""
    from Tooling.core.cli import diagnose, run as _run
    db.insert_goal(conn, problem="p", slug="main",
                   lean_path="Problems/p/Root.lean", statement="T",
                   origin="root", depth=0)
    _open_theorize(conn, workspace)
    payload = diagnose._status_payload(conn, "p")
    assert payload["exists"] is True
    # `daemon status` counts running pipelines; the Theorist is one.
    running, _leases = _run._daemon_counts(workspace)
    assert running >= 1
    status = _run.daemon_status(workspace)
    assert status["in_flight"] >= 1


def test_the_tree_render_is_unmoved_by_a_theory_run(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """A Theorize produces no goal, so TREE has nothing new to say — and
    saying nothing is the correct answer, not an omission: the document
    is listed under `## Notes on this problem`, which is where a reader
    looking for prose goes."""
    from Tooling.state import tree as _tree
    db.insert_goal(conn, problem="p", slug="main",
                   lean_path="Problems/p/Root.lean", statement="T",
                   origin="root", depth=0)
    before = _tree.render(conn, "p")
    _open_theorize(conn, workspace)
    assert _tree.render(conn, "p") == before


def test_the_batch_surfaces_name_the_open_theory_request(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, tmp_path: Path,
) -> None:
    """An open step with no product renders as running — correct, since
    a theory request has no parked state — and the companion carries the
    request itself, because a Theorize has no `brief` column and a step
    shown with "(no brief)" reads as a step about nothing."""
    from Tooling.agent import phase2_context
    _theorize(conn, workspace)
    attempts = tmp_path / "_ctx"
    attempts.mkdir()
    lines = phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts)
    text = "\n".join(lines)
    assert "Dispatched, still running" in text
    companion = (attempts / "BATCHES.md").read_text(encoding="utf-8")
    assert "Theorize — a question for the theory layer" in companion
    assert "**objective** — S such that S implies MAIN" in companion
    assert "**situation** — the bridge died at PAST 3" in companion


def test_a_finished_theory_request_reaches_the_completed_batches(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`## Completed Inject batches` is where a wake reads what its last
    batch left. An accepted document must arrive there by its PATH — the
    thing the next wake opens — and a refused one by its reason."""
    from Tooling.agent import phase2_context
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_clear()])
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    attempts = tmp_path / "_ctx2"
    attempts.mkdir()
    text = "\n".join(phase2_context._section_inject_batch_outcomes(
        conn, "p", workspace=workspace,
        group_id=groups_mod.ensure_top_group(conn, "p"),
        attempts_dir=attempts))
    assert "Completed Inject batches" in text
    assert "THEORY request — objective: S such that S implies MAIN" in text
    path = conn.execute("SELECT path FROM theory_documents").fetchone()[0]
    assert f"document: `{path}`" in text


def test_a_refused_theory_request_says_so_on_the_scoreboard(
    workspace: Path, conn: sqlite3.Connection,
    pintent: intent.ProblemIntent, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    did = _theorize(conn, workspace)
    fake, _ = _script(verdicts=[_fired("1")] * 4)
    monkeypatch.setattr(agent, "spawn_llm", fake)
    _run(conn, workspace, pintent, did)

    attempts = tmp_path / "_ctx3"
    attempts.mkdir()
    text = "\n".join(_batch_section(conn, workspace, attempts))
    assert theorist.REJECTED_DETAIL in text
    assert "the relation is not argued" in text


def test_carry_places_the_new_table(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """`asterism carry` refuses to run on a table it cannot place, and
    the placement is DERIVED — `theory_documents` carries a `problem`
    column, so it is problem-keyed with nothing to declare by hand."""
    from Tooling.state import carry as _carry
    kinds = _carry.assert_classified(conn)
    assert kinds["theory_documents"] == _carry.PROBLEM_KEYED
