"""`lab/continuity.py` + `lab/session_resume.py` — the two kinds that
run one review round twice, resumed against fresh.

A DRY SMOKE, not a provider test. What has to hold before any gpt quota
is spent on this experiment is mechanical and checkable in milliseconds:
the historical session lands where codex looks for it, the round's COLD
spawn is the one rewritten (and the round's own retry is not), a leg
that never reached a spawn is refused rather than filed as the
treatment, and the chain walks its steps in the order the run depends
on. Every test here runs against a fake `spawn_llm` and a hand-written
rollout; nothing spawns.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.lab import LabError
from Tooling.lab import continuity as cont
from Tooling.lab import session_resume as sess
from Tooling.lab import driver as driver_mod
from Tooling.lab import spec as spec_mod

THREAD = "01a06d6b-2e71-7613-8d2e-d487fa4497e0"
ROLLOUT_NAME = f"rollout-2026-09-05T01-15-35-{THREAD}.jsonl"


def _rollout(dirpath: Path, *, turns: int = 1, name: str = ROLLOUT_NAME,
             cumulative=(1000, 900, 50)) -> Path:
    """A rollout with `turns` completed turns, in codex's own shape.

    The running totals grow per turn, because the whole point of the
    usage ledger is that codex reports the CONVERSATION's totals and the
    lab has to hand the adapter a baseline to subtract."""
    total_in, cached, out = cumulative
    lines = [{"timestamp": "2026-09-05T01:15:35.000Z", "ordinal": 0,
              "type": "session_meta",
              "payload": {"session_id": name.rsplit("-", 5)[-5:] and
                          name[len("rollout-2026-09-05T01-15-35-"):-len(
                              ".jsonl")],
                          "cwd": "D:\\Asterism\\.attempts\\old"}}]
    ordinal = 1
    for turn in range(1, turns + 1):
        lines += [
            {"ordinal": ordinal, "type": "event_msg",
             "payload": {"type": "task_started", "turn_id": f"t{turn}"}},
            {"ordinal": ordinal + 1, "type": "response_item",
             "payload": {"type": "message", "role": "assistant"}},
            {"ordinal": ordinal + 2, "type": "token_usage_record",
             "payload": {"thread_id": THREAD,
                         "thread_token_usage": {
                             "input_tokens": total_in * turn,
                             "cached_input_tokens": cached * turn,
                             "cache_write_input_tokens": 0,
                             "output_tokens": out * turn,
                             "total_tokens": (total_in + out) * turn}}},
            {"ordinal": ordinal + 3, "type": "event_msg",
             "payload": {"type": "task_complete", "turn_id": f"t{turn}"}},
        ]
        ordinal += 4
    dirpath.mkdir(parents=True, exist_ok=True)
    path = dirpath / name
    path.write_text("\n".join(json.dumps(o) for o in lines) + "\n",
                    encoding="utf-8")
    return path


class _Spawn:
    """A fake `Tooling.agent.spawn_llm` that records its kwargs."""

    def __init__(self, rc: int = 0):
        self.calls: "list[dict]" = []
        self.rc = rc

    def __call__(self, **kw):
        self.calls.append(dict(kw))
        return self.rc


# ---------------------------------------------------------------------
# staging: the four things a codex resume actually needs
# ---------------------------------------------------------------------

def test_staging_puts_the_session_exactly_where_codex_looks_for_it(
        tmp_path):
    """codex resolves a resumed thread by OPENING ITS ROLLOUT under
    `CODEX_HOME/sessions/YYYY/MM/DD/`; with the file anywhere else the
    spawn dies in seconds with `failed to resolve rollout path`. The
    date comes off the filename, which is the only place it is."""
    src = _rollout(tmp_path / "archive")
    attempts = tmp_path / "ws" / ".attempts" / "pid"
    attempts.mkdir(parents=True)

    got = sess.stage_resume(attempts, sid="SID-1", rollout=src)

    home, session_map, usage_ledger = sess._codex_names()
    staged = (attempts / home / "sessions" / "2026" / "09" / "05"
              / ROLLOUT_NAME)
    assert staged.is_file()
    assert got["thread_id"] == THREAD
    assert json.loads((attempts / session_map).read_text(
        encoding="utf-8")) == {"SID-1": THREAD}
    # The baseline, so `spawn_usage` is billed for THIS turn and not for
    # the conversation (measured 2.0x over-bill, 2026-08-15).
    assert json.loads((attempts / usage_ledger).read_text(
        encoding="utf-8"))[THREAD]["cache_read_input_tokens"] == 900


def test_the_usage_baseline_takes_the_cached_half_out_of_the_prompt():
    """codex's `input_tokens` INCLUDES the cached ones and the parser's
    does not. A baseline carried across raw would subtract the cached
    prompt twice and report a resumed turn as free."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        src = _rollout(Path(d), turns=2)
        base = sess.rollout_baseline(src)
    assert base == {"input_tokens": 200, "cache_read_input_tokens": 1800,
                    "cache_creation_input_tokens": 0,
                    "output_tokens": 100}


def test_a_rollout_that_is_not_one_is_refused_by_name(tmp_path):
    bad = tmp_path / "session.jsonl"
    bad.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not a codex rollout"):
        sess.thread_of(bad)


def test_the_longest_copy_of_a_thread_wins(tmp_path):
    """A resumed turn APPENDS to the same file under the same name, so
    when a predecessor arm's `_out/` and the live archive both hold this
    thread, the longer one IS the later state of the conversation.
    Picking by mtime would pick whichever copy was made last."""
    old = _rollout(tmp_path / "archive", turns=1)
    new = _rollout(tmp_path / "prior_run", turns=3)
    assert new.stat().st_size > old.stat().st_size

    picked, seen = sess.find_rollout(
        [tmp_path / "prior_run", tmp_path / "archive"], THREAD)

    assert picked == new
    assert len(seen) == 2


def test_a_thread_with_no_rollout_says_what_it_needs_and_where(tmp_path):
    with pytest.raises(SystemExit, match="failed to resolve rollout path"):
        sess.find_rollout([tmp_path], THREAD)


def test_a_session_is_cut_at_a_turn_boundary_not_at_a_byte(tmp_path):
    """The Theorist's author holds ONE thread across every revision turn
    of an episode. An arm resuming it to answer round 2 would resume an
    author that already wrote rounds 3 and 4 — so the cut exists; and it
    lands after a completed turn, because a replay whose last tool call
    has no result is refused by the provider."""
    src = _rollout(tmp_path / "archive", turns=4)
    dst = tmp_path / "cut" / ROLLOUT_NAME

    note = sess.truncate_rollout(src, dst, 2)

    kinds = [json.loads(x)["type"] for x in
             dst.read_text(encoding="utf-8").splitlines()]
    assert note["turns_kept"] == 2
    assert kinds[0] == "session_meta"           # the header survives
    assert kinds[-1] == "event_msg"             # ...and it ends on one
    assert json.loads(dst.read_text(encoding="utf-8").splitlines()[-1]
                      )["payload"]["type"] == "task_complete"
    assert sess.rollout_baseline(dst)["output_tokens"] == 100


def test_a_cut_past_the_end_of_a_session_is_refused(tmp_path):
    src = _rollout(tmp_path / "archive", turns=1)
    with pytest.raises(SystemExit, match="holds 1 completed turn"):
        sess.truncate_rollout(src, tmp_path / "cut" / ROLLOUT_NAME, 3)


# ---------------------------------------------------------------------
# the seam: which spawn gets rewritten
# ---------------------------------------------------------------------

@pytest.mark.parametrize("seat,kind", [
    ("theory_reviewer", "theory_review_round"),
    ("adversary", "judge_review_round"),
])
def test_a_resumed_leg_reaches_the_seats_cold_spawn_with_the_session(
        tmp_path, monkeypatch, seat, kind):
    """THE DRY SMOKE, per kind. `resume_sid` has to arrive at the spawn
    as `session_id` + `continuation=True` — the adapter resumes on
    exactly that pair (`resuming = bool(prior) and (is_retry or
    continuation or is_postmortem)`) — and the session dir has to be
    staged into the dir that spawn will use."""
    import Tooling.agent as agent_mod

    src = _rollout(tmp_path / "archive")
    proj = tmp_path / "ws" / ".attempts" / "pid" / "r2"
    proj.mkdir(parents=True)
    fake = _Spawn()
    monkeypatch.setattr(agent_mod, "spawn_llm", fake)

    with sess.resume_cold_spawn(kinds=(seat,), rollout=src,
                                session_id="SID-9", label=kind) as state:
        # what the production round function does on a cold try
        agent_mod.spawn_llm(kind=seat, prompt_path=tmp_path / "p.md",
                            problem_dir=proj, attempts_dir=proj,
                            session_id="a-fresh-uuid", is_retry=False)

    assert state["fired"] == 1
    assert state["thread_id"] == THREAD
    call = fake.calls[0]
    assert call["session_id"] == "SID-9"
    assert call["continuation"] is True
    home, session_map, _ = sess._codex_names()
    assert (proj / home / "sessions" / "2026" / "09" / "05"
            / ROLLOUT_NAME).is_file()
    assert json.loads((proj / session_map).read_text(
        encoding="utf-8")) == {"SID-9": THREAD}
    # ...and the wrapper is gone afterwards.
    assert agent_mod.spawn_llm is fake


def test_the_rounds_own_retry_and_the_feedback_turn_are_left_alone(
        tmp_path, monkeypatch):
    """`is_retry` is the round handing a refused verdict back to the
    judge it just had, and `is_postmortem` is the feedback turn. Both
    already resume; rewriting either would put the HISTORICAL session in
    front of a prompt written for a different conversation."""
    import Tooling.agent as agent_mod

    src = _rollout(tmp_path / "archive")
    proj = tmp_path / "proj"
    proj.mkdir()
    fake = _Spawn()
    monkeypatch.setattr(agent_mod, "spawn_llm", fake)

    with sess.resume_cold_spawn(kinds=("adversary",), rollout=src,
                                session_id="SID-9") as state:
        agent_mod.spawn_llm(kind="adversary", attempts_dir=proj,
                            session_id="cold", is_retry=False)
        agent_mod.spawn_llm(kind="adversary", attempts_dir=proj,
                            session_id="cold", is_retry=True,
                            retry_context="rewrite it")
        agent_mod.spawn_llm(kind="adversary", attempts_dir=proj,
                            session_id="cold", is_postmortem=True)
        # another seat's spawn in the same block is not this leg's
        agent_mod.spawn_llm(kind="strategist", attempts_dir=proj,
                            session_id="cold")

    assert state["fired"] == 1
    assert [c.get("continuation") for c in fake.calls] == [
        True, None, None, None]
    assert [c["session_id"] for c in fake.calls] == [
        "SID-9", "cold", "cold", "cold"]


def test_a_resumed_leg_that_never_spawned_refuses_instead_of_reporting(
        tmp_path, monkeypatch):
    """A wrapper that silently never matched is a resumed arm that ran
    FRESH and got filed as the treatment — the one failure that would
    make the whole experiment's readout wrong and look right."""
    import Tooling.agent as agent_mod

    src = _rollout(tmp_path / "archive")
    monkeypatch.setattr(agent_mod, "spawn_llm", _Spawn())
    with pytest.raises(SystemExit, match="never reached a cold"):
        with sess.resume_cold_spawn(kinds=("adversary",), rollout=src,
                                    label="adversary r2"):
            pass


def test_a_seat_that_is_not_on_codex_is_refused_before_the_round_runs(
        monkeypatch, tmp_path):
    """A `--seats theory_reviewer=claude/...` override would otherwise
    build the dossier, spawn a cold judge and report the arm's name over
    a run with no resume in it."""
    from Tooling.llm import capabilities as caps
    monkeypatch.setattr(caps, "provider_for_kind",
                        lambda kind, ws=None: "claude")
    with pytest.raises(SystemExit, match="not codex rollouts"):
        sess.assert_resumable_seat("theory_reviewer", tmp_path)
    monkeypatch.setattr(caps, "provider_for_kind",
                        lambda kind, ws=None: "codex")
    assert sess.assert_resumable_seat("adversary", tmp_path) == "codex"


# ---------------------------------------------------------------------
# the chain
# ---------------------------------------------------------------------

def test_the_three_chain_shapes_are_the_ones_the_experiment_needs():
    assert cont.plan_chain("pair", 2) == [{"step": "pair", "round": 2}]
    assert cont.plan_chain("revise_then_pair", 3) == [
        {"step": "revise", "round": 3}, {"step": "pair", "round": 3}]
    assert cont.plan_chain("pair_revise_pair", 2) == [
        {"step": "pair", "round": 2}, {"step": "revise", "round": 3},
        {"step": "pair", "round": 3}]
    with pytest.raises(SystemExit, match="unknown chain"):
        cont.plan_chain("both", 1)


def _verdict(tag: str, ruling: str = "rebut") -> dict:
    return {"verdict": ruling, "criticisms": [f"fired: {tag}"],
            "reservations": [], "criteria": {"1": [f"fired: {tag}"]}}


def test_a_chain_runs_resumed_first_and_feeds_the_revision_from_it(
        tmp_path):
    """The run order that defines this experiment: `resumed` is the
    treatment and the chain's next step is fed from ITS verdict. A chain
    fed from `fresh` would be measuring the control's downstream
    effect."""
    out = tmp_path / "_out"
    seen: "list[tuple]" = []
    fed: "list[dict]" = []

    def judge(round_no, leg, resumed):
        seen.append(("judge", round_no, leg, resumed))
        return {"verdict": _verdict(f"r{round_no}-{leg}"), "rc": 0,
                "pipeline_id": f"p{round_no}{leg}"}

    def revise(round_no, verdict):
        seen.append(("revise", round_no, None, None))
        fed.append(verdict)
        return {"rc": 0, "body": f"# proposal r{round_no}\n",
                "pipeline_id": "author"}

    result = cont.run_chain(chain="pair_revise_pair", round_no=2, out=out,
                            judge=judge, revise=revise,
                            revision_basename="proposal_r3.md")

    assert seen == [("judge", 2, "resumed", True),
                    ("judge", 2, "fresh", False),
                    ("revise", 3, None, None),
                    ("judge", 3, "resumed", True),
                    ("judge", 3, "fresh", False)]
    assert fed == [_verdict("r2-resumed")]
    assert result["outcome"] == "success"
    for name in ("verdict_r2_resumed.json", "verdict_r2_fresh.json",
                 "verdict_r3_resumed.json", "verdict_r3_fresh.json",
                 "verdict_r2_resumed.md", "timing.json", "rounds.json",
                 "proposal_r3.md"):
        assert (out / name).is_file(), name
    # The headline pair the run order names is the arm's LAST round —
    # the one it exists to compare.
    assert json.loads((out / "verdict_resumed.json").read_text(
        encoding="utf-8")) == _verdict("r3-resumed")
    timing = json.loads((out / "timing.json").read_text(encoding="utf-8"))
    assert {leg["leg"] for leg in timing["legs"]} == {"resumed", "fresh"}
    assert "r3_wall_delta_sec" in timing


def test_a_chain_that_owes_a_revision_with_no_verdict_is_refused(tmp_path):
    """`revise_then_pair` answers the verdict its PREDECESSOR produced.
    Started without one, the author would spend a turn on an empty
    rebuttal and the arm would report a round it never argued."""
    with pytest.raises(SystemExit, match="owes the author a revision"):
        cont.run_chain(chain="revise_then_pair", round_no=3,
                       out=tmp_path / "_out",
                       judge=lambda *a: {"verdict": _verdict("x")},
                       revise=lambda *a: {"rc": 0, "body": ""})


def test_a_leg_that_produced_no_ruling_still_leaves_its_file(tmp_path):
    """A chain that dies part-way is exactly the run worth reading, and
    the workspace is cleared behind it."""
    out = tmp_path / "_out"
    result = cont.run_chain(
        chain="pair", round_no=1, out=out,
        judge=lambda n, leg, r: {"verdict": None, "rc": 1,
                                 "err": "no verdict.json"},
        revise=lambda *a: {})
    assert result["outcome"] == "failed"
    assert json.loads((out / "verdict_r1_fresh.json").read_text(
        encoding="utf-8"))["_no_verdict"] == "no verdict.json"


# ---------------------------------------------------------------------
# continuing the arm before this one
# ---------------------------------------------------------------------

def _run_dir(root: Path, exp: str, arm: str, rep: int,
             record: "dict | None" = None) -> Path:
    d = root / "runs" / exp / f"{arm}_r{rep}"
    (d / "_out").mkdir(parents=True)
    if record is not None:
        (d / "_out" / "run_record.json").write_text(
            json.dumps(record), encoding="utf-8")
    (d / "workspace.json").write_text(
        json.dumps({"experiment": exp, "arm": arm, "rep": rep}),
        encoding="utf-8")
    return d


def test_a_chained_arm_finds_its_predecessor_from_where_it_stands(
        tmp_path):
    """The driver is handed a spec, not a lab root — the root lives in
    the operator's development area and nothing may compile a default
    for it. It is derived from `<root>/runs/<exp>/<arm>_r<n>` instead,
    which names no path and invents no default."""
    root = tmp_path / "lab"
    _run_dir(root, "jc", "theorist_a", 1, {"outcome": "success"})
    ws = _run_dir(root, "jc", "theorist_b", 1)

    got_root, exp, arm = cont.locate_lab(ws)

    assert got_root == root.resolve() and exp == "jc" and arm == "theorist_b"
    assert cont.find_prior_run(root, "jc", "theorist_a").name ==         "theorist_a_r1"


def test_an_unfinished_predecessor_is_not_a_predecessor(tmp_path):
    """Finished means the pair that survives a run is there. A workspace
    still standing has no record to answer with."""
    root = tmp_path / "lab"
    _run_dir(root, "jc", "theorist_a", 1)          # no run_record.json
    with pytest.raises(SystemExit, match="no finished run of arm"):
        cont.find_prior_run(root, "jc", "theorist_a")
    with pytest.raises(SystemExit, match="no runs of"):
        cont.find_prior_run(root, "other", "theorist_a")


def test_the_verdict_a_chained_arm_answers_is_the_resumed_one(tmp_path):
    prior = _run_dir(tmp_path, "jc", "theorist_a", 1, {"outcome": "ok"})
    (prior / "_out" / "verdict_resumed.json").write_text(
        json.dumps(_verdict("r2")), encoding="utf-8")
    assert cont.incoming_verdict(prior) == _verdict("r2")


def test_a_predecessor_that_passed_gives_the_author_nothing_to_answer(
        tmp_path):
    """The revision step would spend a turn on an empty rebuttal and the
    arm would report a round it never argued."""
    prior = _run_dir(tmp_path, "jc", "theorist_a", 1, {"outcome": "ok"})
    (prior / "_out" / "verdict_resumed.json").write_text(
        json.dumps({"verdict": "pass", "criticisms": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="carries no criticisms"):
        cont.incoming_verdict(prior)


# ---------------------------------------------------------------------
# the lab.yaml these arms are written in
# ---------------------------------------------------------------------

def test_both_kinds_are_declared_and_implemented():
    """`lab.yaml` validates `kind:` against `spec.DRIVER_KINDS` and the
    driver dispatches on `driver.KINDS`; a kind in one and not the other
    is an arm that validates and then dies in the workspace it just
    built."""
    for kind in ("theory_review_round", "judge_review_round"):
        assert kind in spec_mod.DRIVER_KINDS
        assert kind in driver_mod.KINDS


def _opts(tmp_path, **over) -> dict:
    (tmp_path / "report.md").write_text("# draft\n", encoding="utf-8")
    opts = {"group": "root", "resume_sid": THREAD,
            "sessions_root": str(tmp_path), "report": "report.md",
            "request": {"objective": "settle it", "situation": "here"}}
    opts.update(over)
    return opts


def test_an_arm_missing_the_session_it_resumes_is_refused_at_the_yaml(
        tmp_path):
    opts = _opts(tmp_path)
    opts.pop("resume_sid")
    with pytest.raises(LabError, match="`resume_sid:` is required"):
        cont.check_options("a", "theory_review_round", opts, tmp_path)


def test_a_chained_arm_must_say_which_arm_it_continues(tmp_path):
    opts = _opts(tmp_path, chain="revise_then_pair",
                 author_resume_sid=THREAD)
    with pytest.raises(LabError, match="from_arm"):
        cont.check_options("b", "theory_review_round", opts, tmp_path)


def test_a_chain_with_an_author_turn_needs_the_authors_own_session(
        tmp_path):
    opts = _opts(tmp_path, chain="pair_revise_pair")
    with pytest.raises(LabError, match="author_resume_sid"):
        cont.check_options("c", "theory_review_round", opts, tmp_path)


def test_an_input_file_is_resolved_beside_the_lab_yaml(tmp_path):
    opts = _opts(tmp_path)
    cont.check_options("a", "theory_review_round", opts, tmp_path)
    assert opts["report"] == str((tmp_path / "report.md").resolve())
    opts["report"] = "nowhere.md"
    with pytest.raises(LabError, match="no report file at"):
        cont.check_options("a", "theory_review_round", opts, tmp_path)


def test_a_reference_file_rides_into_the_record_and_reaches_no_agent(
        tmp_path):
    """The HISTORICAL ruling on this very round is the third term both
    verdicts are read against, and a comparison whose third term has to
    be re-queried is one nobody makes."""
    (tmp_path / "hist.json").write_text("{}", encoding="utf-8")
    opts = _opts(tmp_path, reference=["hist.json"])
    cont.check_options("a", "theory_review_round", opts, tmp_path)
    out = tmp_path / "_out"
    kept = cont.copy_inputs(opts, out, ("report", "dialogue"))
    assert sorted(kept) == ["inputs/hist.json", "inputs/report.md"]
    assert (out / "inputs" / "hist.json").is_file()
    opts["reference"] = "hist.json"          # not a list
    with pytest.raises(LabError, match="a LIST of files"):
        cont.check_options("a", "theory_review_round", opts, tmp_path)


def test_an_unknown_chain_is_named_at_the_yaml_not_in_the_workspace(
        tmp_path):
    opts = _opts(tmp_path, chain="pair_pair")
    with pytest.raises(LabError, match="is not one of"):
        cont.check_options("a", "theory_review_round", opts, tmp_path)


def test_a_theory_arm_without_the_request_is_refused(tmp_path):
    opts = _opts(tmp_path, request={"situation": "here"})
    with pytest.raises(LabError, match="objective"):
        cont.check_options("a", "theory_review_round", opts, tmp_path)


def test_a_lab_yaml_declaring_a_continuity_arm_loads(tmp_path):
    """End to end through the validator the operator actually meets."""
    docs = tmp_path / "docs" / "jc"
    docs.mkdir(parents=True)
    (docs / "proposal.md").write_text("# proposal\n", encoding="utf-8")
    (docs / "lab.yaml").write_text(
        "snapshot: X@1\n"
        "arms:\n"
        "  strategist_c:\n"
        "    kind: judge_review_round\n"
        "    group: 691\n"
        "    round_no: 2\n"
        "    chain: pair_revise_pair\n"
        "    proposal: proposal.md\n"
        f"    sessions_root: {Path(tmp_path).as_posix()}\n"
        f"    resume_sid: {THREAD}\n"
        f"    author_resume_sid: {THREAD}\n"
        "    resume_note: criterion 5 retired after this session ran\n"
        "    seats:\n"
        "      adversary: codex/gpt-5.6-sol:high\n",
        encoding="utf-8")

    exp = spec_mod.load(tmp_path, "jc")

    arm = exp.arm("strategist_c")
    assert arm.kind == "judge_review_round"
    assert arm.option("chain") == "pair_revise_pair"
    assert arm.seats["adversary"] == {"provider": "codex",
                                      "model": "gpt-5.6-sol",
                                      "reasoning_effort": "high"}
    assert arm.option("proposal") == str((docs / "proposal.md").resolve())
