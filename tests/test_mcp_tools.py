"""The framework's tool surface over MCP — the whitelist's new home.

A shell allowlist is only a control where the provider can express one.
claude's matcher takes `<prefix> *`; the Antigravity CLI's takes an exact
literal or `*` and nothing between (measured 2026-07-30), so "loogle only"
was inexpressible there and the run went out with `command(*)`. Within a
day that cost a Strategist wake 32 minutes to an agent-authored `python -c`
loop scanning to 10**15 — a compute channel, where all the design
attention had gone to the write channel.

These tests pin the replacement: one tool list, same for every provider,
with the framework owning the command line.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _tool_names() -> "set[str]":
    """The server's actual tool list."""
    import asyncio

    from Tooling.knowledge import mcp_tools
    return {t.name for t in asyncio.run(mcp_tools.mcp.list_tools())}


def test_server_exposes_exactly_the_intended_tools() -> None:
    """The tool list IS the whitelist. Adding one is a deliberate act,
    so it fails here first — which is the difference between this and a
    permission file nobody rereads."""
    import asyncio

    from Tooling.knowledge import mcp_tools

    tools = asyncio.run(mcp_tools.mcp.list_tools())
    assert {t.name for t in tools} == {
        "loogle", "validate_json",
        # The shell's replacements (2026-08-10): reading, calculating,
        # and the Scholar's two curated network commands, which had to
        # move here or closing Bash would decapitate that role.
        "inspect", "compute", "paper_search", "paper_fetch",
        # The server-side write (2026-08-17): codex's Windows sandbox
        # blocks a session's FIRST apply_patch for the whole sandbox
        # warm-up (measured 142.6s, growing day over day), agents give
        # up, and the wake dies as `agent_no_output`. This write runs
        # in the tools server's process, outside that sandbox, and only
        # into the spawn's own attempts dir.
        "write_file",
        # The Assistant's surface (2026-09-02, HID §1.1/§3.5/§3.8). The
        # seat gate keeps these off every worker and keeps the workers'
        # write/compute channels off the Assistant; this list is the
        # union, which is why they appear here.
        "write_project_doc", "list_project_docs", "read_project_doc",
        "prepare_command", "daemon_status",
    }


def test_validate_json_covers_the_most_used_shell_call() -> None:
    """`python -m json.tool` was the single most-used command across the
    07-30 agy legs (~47 of ~104), ahead of loogle — agents check their
    own decision.json parses rather than spend a round on a rejection.
    Denying the shell without replacing this would trade a measured
    behaviour for the theory that the framework's parse error suffices."""
    from Tooling.knowledge import mcp_tools

    assert mcp_tools.validate_json('{"a": 1, "b": 2}') == "OK: 2 top-level key(s)"
    assert mcp_tools.validate_json("[1,2,3]") == "OK: array of 3"
    bad = mcp_tools.validate_json('{"a": }')
    assert bad.startswith("INVALID:") and "line" in bad


def test_validate_json_file_mode_reads_the_disk(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disk is the authority (same rule as validate_file, owner call
    2026-08-25): long payloads pasted through tool-call escaping made
    the text mode report offsets that do not exist in the real file —
    `file` validates the bytes actually being handed in. Control chars
    inside strings pass, mirroring every framework parser of agent
    JSON (p324 class); structural damage still fails."""
    from Tooling.knowledge import mcp_tools, workspace_query

    monkeypatch.setattr(workspace_query, "_own_attempt_dir",
                        lambda: tmp_path)
    (tmp_path / "verdict.json").write_text(
        '{"criteria": {"1": "clear", "2": "clear", "3": "clear",'
        ' "4": "clear", "5": "line\none"}}', encoding="utf-8")
    out = mcp_tools.validate_json(file="verdict.json")
    assert out.startswith("OK"), out
    (tmp_path / "cut.json").write_text('{"a": ', encoding="utf-8")
    assert mcp_tools.validate_json(file="cut.json").startswith("INVALID")
    missing = mcp_tools.validate_json(file="nope.json")
    assert "no file at" in missing and "write it first" in missing
    outside = mcp_tools.validate_json(file="../elsewhere.json")
    assert "only your attempts directory" in outside


def test_validate_json_reads_a_theory_verdict_as_a_theory_verdict(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dispatch by OWNERSHIP, never by shape.

    The routine-audit branch used to claim any verdict whose criterion
    3 is a list and which has no criterion 5 — which is exactly a
    theory-wake verdict (criteria "1".."3" or "1".."4", string
    bullets). So the tool told the arm3h_r2 judge, twice, to turn its
    criterion 3 into `{goal_id, verdict, reason}` objects and add a
    criterion 4 it does not have (record:
    `docs/internal/experiments/theory_wake/runs/arm3h_r2_failed/RECOVERED.md`).
    The audit parser's own input — `_audit_roots.json`, written into
    the attempts dir by the routine wake and by nothing else — is the
    signal that this spawn IS the auditor. No snapshot, not an audit.
    """
    from Tooling.knowledge import mcp_tools, workspace_query

    monkeypatch.setattr(workspace_query, "_own_attempt_dir",
                        lambda: tmp_path)
    (tmp_path / "verdict.json").write_text(json.dumps({"criteria": {
        "1": ["clear: the same-universe theorem supplies the bound"],
        "2": ["clear: I re-enumerated all 2^16 families on four points"],
        "3": ["clear: the wall is named as the restoration statement"],
        "4": ["clear: the rank-three conjecture is motivated by Thm 2",
              "clear: the cross-trace lead follows from the equality"]},
        "reservations": []}), encoding="utf-8")
    out = mcp_tools.validate_json(file="verdict.json")
    assert "audit" not in out.lower(), out
    assert "criterion 4" not in out, out
    assert "goal_id" not in out, out


# ------------------------------------------ the declared verdict rubric

_REVIEW_VERDICT = {"criteria": {
    "1": ["clear: the same-universe theorem supplies the bound"],
    "2": ["clear: I re-enumerated all 2^16 families on four points"],
    "3": ["fired: the wall named in §2 is not the one that bites"],
    "4": ["clear: the rank-three conjecture is motivated by Thm 2",
          "clear: the cross-trace lead follows from the equality"]},
    "reservations": []}


def _seat(monkeypatch, tmp_path, verdict, rubric=None) -> str:
    from Tooling.knowledge import mcp_tools, workspace_query
    monkeypatch.setattr(workspace_query, "_own_attempt_dir",
                        lambda: tmp_path)
    (tmp_path / "verdict.json").write_text(json.dumps(verdict),
                                           encoding="utf-8")
    if rubric is not None:
        (tmp_path / "_verdict_rubric.json").write_text(
            json.dumps(rubric), encoding="utf-8")
    return mcp_tools.validate_json(file="verdict.json")


def test_a_declared_rubric_is_the_key_set_the_verdict_is_checked_against(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The generic branch assumes the batch judge's rubric 1-5, so a
    theory-review verdict — criteria "1".."4", complete — was told
    "`criteria` missing criterion 5": a framework fault worded as the
    judge's mistake, on a rubric the judge cannot add a criterion to.

    Shape cannot answer this ("1".."4" is also a batch verdict with one
    criterion missing), so the wake that seats the judge DECLARES its
    rubric — `_verdict_rubric.json` in the review dir, the same
    ownership signal as `_audit_roots.json` one layer up."""
    out = _seat(monkeypatch, tmp_path, _REVIEW_VERDICT,
                {"criteria_keys": ["1", "2", "3", "4"],
                 "multi_clear": True})
    assert out.startswith("OK"), out
    assert "review-shaped" in out and "1–4" in out, out
    assert "criterion 5" not in out and "missing" not in out, out


def test_a_declared_rubric_still_refuses_a_key_it_declares(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declaration narrows the key set; it does not switch the check
    off. The criterion named is one the judge can actually write."""
    verdict = {"criteria": {k: v
                            for k, v in _REVIEW_VERDICT["criteria"].items()
                            if k != "3"}, "reservations": []}
    out = _seat(monkeypatch, tmp_path, verdict,
                {"criteria_keys": ["1", "2", "3", "4"],
                 "multi_clear": True})
    assert "missing criterion 3" in out and "reject" in out, out
    assert "5" not in out, out


def test_a_declared_rubric_refuses_a_bare_clear_and_a_mixed_criterion(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two rules the real parser enforces and a judge loses a whole
    round to: a criterion is one ruling, and "clear" alone leaves no
    calibration trace."""
    rubric = {"criteria_keys": ["1", "2", "3", "4"], "multi_clear": True}
    bare = {"criteria": dict(_REVIEW_VERDICT["criteria"], **{"2": ["clear"]}),
            "reservations": []}
    out = _seat(monkeypatch, tmp_path, bare, rubric)
    assert "criterion 2" in out and "bare" in out, out
    mixed = {"criteria": dict(_REVIEW_VERDICT["criteria"],
                              **{"4": ["clear: it follows from Thm 2",
                                       "fired: lead three is unmotivated"]}),
             "reservations": []}
    out = _seat(monkeypatch, tmp_path, mixed, rubric)
    assert "criterion 4" in out and "mixes" in out, out


def test_a_declared_rubric_holds_the_string_bullet_it_declared(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The declaration says STRING bullets, so this probe says string
    bullets — even though the review parser also tolerates an
    object-rendered bullet. A probe that is looser than the declaration
    teaches a shape the declaration does not promise to keep, and the
    teaching text names the shape to write rather than only refusing."""
    obj_bullets = {"criteria": dict(
        _REVIEW_VERDICT["criteria"],
        **{"1": [{"ruling": "clear", "reason": "the bound is supplied"}]}),
        "reservations": []}
    out = _seat(monkeypatch, tmp_path, obj_bullets,
                {"criteria_keys": ["1", "2", "3", "4"],
                 "multi_clear": True})
    assert "criterion 1" in out and "reject" in out, out
    assert "string" in out.lower() and "clear:" in out, out


def test_no_declaration_leaves_the_batch_judge_check_exactly_as_it_was(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The channel is opt-in: a spawn with no declaration is the batch
    judge, and its rubric is still 1-5. A malformed declaration counts
    as absent — the judge did not write that file and cannot repair
    it, so it must never become a refusal with no action behind it."""
    batch = {"criteria": {str(k): ["clear: a concrete reason"]
                          for k in range(1, 6)}, "reservations": []}
    out = _seat(monkeypatch, tmp_path, batch)
    assert out.endswith("criteria 1-5 all present"), out
    four = {"criteria": {str(k): ["clear: a concrete reason"]
                         for k in range(1, 5)}, "reservations": []}
    assert "missing criterion 5" in _seat(monkeypatch, tmp_path, four)
    (tmp_path / "_verdict_rubric.json").write_text("{ not json",
                                                   encoding="utf-8")
    assert "missing criterion 5" in _seat(monkeypatch, tmp_path, four)


def test_loogle_tool_reports_failure_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead network is an answer the agent can act on; an exception
    across the MCP boundary is not."""
    from Tooling.knowledge import loogle as _loogle
    from Tooling.knowledge import mcp_tools

    monkeypatch.setattr(_loogle, "query",
                        lambda *a, **k: (1, "loogle network error: boom"))
    out = mcp_tools.loogle("Nat.succ _")
    assert "unavailable" in out and "boom" in out


def test_loogle_tool_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agent pays for every byte in its next turn, so the cap is the
    framework's job — it owns the call now, which is the whole point."""
    from Tooling.knowledge import loogle as _loogle
    from Tooling.knowledge import mcp_tools

    monkeypatch.setattr(_loogle, "query",
                        lambda *a, **k: (0, "x" * (mcp_tools.MAX_CHARS * 2)))
    out = mcp_tools.loogle("_")
    assert len(out) < mcp_tools.MAX_CHARS + 200
    assert "truncated" in out


def test_tools_config_is_stdio_with_pythonpath(tmp_path: Path) -> None:
    """PYTHONPATH, not cwd: the client spawns the server from the spawn's
    own directory, and neither claude's nor agy's MCP schema carries a
    cwd field."""
    from Tooling import pipeline

    att = tmp_path / "att"
    att.mkdir()
    path = pipeline.write_tools_mcp_config(att, tmp_path,
                                           seat="strategist")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    entry = cfg["mcpServers"]["asterism_tools"]
    assert entry["type"] == "stdio"
    assert entry["args"] == ["-m", "Tooling.knowledge.mcp_tools"]
    assert entry["env"]["PYTHONPATH"] == str(tmp_path)
    assert entry["env"]["ASTERISM_SEAT"] == "strategist"
    # No gateway session for a wake with no Lean file open — registering
    # one would hold a backend slot for nothing.
    assert set(cfg["mcpServers"]) == {"asterism_tools"}


def test_every_prompt_naming_a_tool_gets_a_config() -> None:
    """Naming a tool in a prompt is a promise the dispatch must keep.

    Caught while landing this change: the librarian and presearch prompts
    were rewritten to call `loogle(...)` while their spawns passed no MCP
    config at all, so the instruction would have named a tool the agent
    could not call — a silent capability gap, the same shape as the
    retired-pipeline vocabulary that told workers about roles that no
    longer existed."""
    repo = Path(__file__).resolve().parents[1]
    prompts = repo / "Tooling" / "prompts"
    # prompt directory -> the module that spawns that kind
    owners = {
        "strategist": ["Tooling/pipeline/strategist/wake.py"],
        "adversary": ["Tooling/pipeline/adversary.py"],
        "librarian": ["Tooling/pipeline/librarian/run.py"],
        "formalizer": ["Tooling/pipeline/_retry.py"],
        # (scholar retired 2026-08-22 — paper_search/paper_fetch are the
        # Strategist's own surface now; its spawn already carries the
        # tools config checked above.)
        "_shared": ["Tooling/pipeline/_presearch.py",
                    "Tooling/pipeline/_retry.py"],
    }
    missing: list[str] = []
    for sub, modules in owners.items():
        names = " ".join(
            p.read_text(encoding="utf-8")
            for p in (prompts / sub).glob("*.md"))
        # Match against the server's REAL tool list, not two names
        # someone remembered to add here. A whitelist test that
        # enumerates by hand is the thing it is supposed to prevent.
        if not any(f"{tool}(" in names for tool in _tool_names()):
            continue
        if not any("mcp_config_path=" in (repo / m).read_text(encoding="utf-8")
                   for m in modules):
            missing.append(f"{sub} prompts name a tool; none of "
                           f"{modules} passes mcp_config_path")
    assert not missing, "\n  ".join(missing)


def test_no_prompt_names_a_shell_command_at_all() -> None:
    """There is no shell to name any more (2026-08-10).

    The earlier version of this pin asked whether every `python -m X` a
    prompt named was still granted somewhere in the claude allowlist —
    the right question while a curated shell existed. `--disallowedTools
    Bash` ended that, so the question becomes absolute: a prompt that
    tells an agent to run anything is telling it to do something it
    cannot do, and the agent will spend a turn discovering that.
    """
    import re

    repo = Path(__file__).resolve().parents[1]
    named: dict[str, str] = {}
    for p in (repo / "Tooling" / "prompts").rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        for mod in re.findall(r"python -m ([\w.]+)", text):
            named.setdefault(mod, p.name)
    assert not named, (
        "prompts still name shell commands, but Bash is denied: "
        + ", ".join(f"{m} ({f})" for m, f in sorted(named.items()))
        + " — point them at the MCP tool instead")


def test_the_bash_deny_and_its_replacement_ship_together() -> None:
    """Closing a channel without naming the replacement is how a gate
    becomes a wall. The deny is in the spawn flags; the way out is in
    spawn_guard's message; both must exist."""
    repo = Path(__file__).resolve().parents[1]
    cli = (repo / "Tooling" / "llm" / "claude_cli.py").read_text(
        encoding="utf-8")
    guard = (repo / "Tooling" / "llm" / "spawn_guard.py").read_text(
        encoding="utf-8")
    deny = cli[cli.index('"--disallowedTools",'):]
    assert '"Bash",' in deny[:2000], "the blanket Bash deny is gone"
    assert "Bash is not available" in guard
    for tool in ("inspect", "compute"):
        assert tool in guard, tool


def test_judge_contract_rides_the_projection_not_the_prompt() -> None:
    """17 lines of decision-kind reference were inlined into every judge
    spawn. They are reference, not instruction, so they move to the
    projection — in their own file: `decisions.md` is what the Strategist
    wrote, and a judge that prosecutes attribution should not find
    framework text inside it."""


    repo = Path(__file__).resolve().parents[1]
    fragment = repo / "Tooling" / "prompts" / "adversary" / "_contract.md"

    assert fragment.exists()
    assert "`Inject` —" in fragment.read_text(encoding="utf-8")


def test_loogle_left_the_shell_allowlist() -> None:
    """The claude side kept a working Bash rule for months; it is removed
    here not because it failed but because it could not be mirrored on the
    other provider, and a control that only one provider honours is not a
    control."""
    from Tooling.llm import claude_cli

    # The allowlist must COVER the server, not match a literal. Pinning
    # the literal is what let `inspect`, `compute` and the two paper
    # tools ship on 2026-08-10 registered but unreachable: this test
    # passed all along because it was checking the wrong side of the
    # relation. On claude an omitted tool prompts, and headless
    # auto-denies the prompt — so g7491's worker asked for `inspect` as
    # its first move after intake, was refused twice, fell back to Grep,
    # and rebuilt a brick it had been told to cite. (The Antigravity
    # side grants `mcp(*)` and was never affected — the asymmetry is
    # exactly why the enumerated side needs a mechanical check.)
    import ast
    from Tooling.knowledge import mcp_tools as _mt
    src = ast.parse(Path(_mt.__file__).read_text(encoding="utf-8"))
    registered = {
        node.name for node in ast.walk(src)
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(d, ast.Call)
                and ((isinstance(d.func, ast.Attribute)
                      and d.func.attr == "tool")
                     or (isinstance(d.func, ast.Name)
                         and d.func.id == "_seat_tool"))
                for d in node.decorator_list)
        and node.name != "_seat_tool"
    }
    assert registered, "no @mcp.tool functions found — parser drifted"
    assert set(claude_cli._TOOLS_MCP_PATTERNS) == {
        f"mcp__asterism_tools__{name}" for name in registered
    }
    # Empty, so an unmatched Bash call falls to the prompt that headless
    # auto-denies. `json.tool` went with loogle once `validate_json`
    # existed — and not for tidiness: `python -m json.tool <in> <out>`
    # writes its OUTFILE, so the trailing `*` was a write channel that
    # two months of comments called side-effect-free.
    assert claude_cli.DEFAULT_BASH_ALLOWED == ""


def test_no_mcp_tool_has_a_required_parameter() -> None:
    """A model guesses parameter names. When it guesses wrong, FastMCP's
    pydantic model raises `Field required` — and on the Antigravity CLI a
    raising MCP tool stamps the WHOLE envelope `status: ERROR`, killing
    the run and the `--resume` turn that would have collected its
    feedback.

    Measured 2026-08-10, first live minute of the Gemini formalizer
    seat: `inspect(inspect_requests=[…])`. Six spawns filed no feedback
    in that fifteen-minute window, and the file already carried the same
    lesson for `loogle(query=…)` — written down, then not applied to the
    next tool. Hence a test rather than a note.

    The rule is not "accept these aliases": enumerating names a model
    might invent is the trap this codebase keeps naming. It is "never
    raise" — every parameter optional, and a call that binds nothing
    answers with a teaching string. Extra unknown fields are already
    dropped by pydantic, so a mis-named argument arrives as an empty
    call, which is exactly the case the teaching string covers."""
    import asyncio

    from Tooling.knowledge import mcp_tools
    from Tooling.lsp import gateway

    offenders: "list[str]" = []
    for server in (mcp_tools.mcp, gateway.mcp):
        for t in asyncio.run(server.list_tools()):
            required = (t.inputSchema or {}).get("required") or []
            if required:
                offenders.append(f"{t.name}: {sorted(required)}")
    assert not offenders, (
        "these MCP tools raise instead of teaching when a model guesses a "
        f"parameter name wrong: {offenders}")


def test_inspect_reads_the_delivery_ceiling_from_its_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backend's transport ceiling reaches the server as
    `ASTERISM_INSPECT_DELIVERY_CHARS` (set by the provider adapter from
    the capability declaration). Unset — an unmeasured backend — must
    arrive as None, never a guessed number; garbage must not raise
    across the MCP boundary."""
    from Tooling.knowledge import mcp_tools, workspace_query

    seen: list = []

    def fake(queries, *, delivery_chars=None, **_kw):
        seen.append(delivery_chars)
        return "ok"

    monkeypatch.setattr(workspace_query, "run_queries", fake)
    monkeypatch.setenv("ASTERISM_INSPECT_DELIVERY_CHARS", "30000")
    assert mcp_tools.inspect([{"size": "."}]) == "ok"
    monkeypatch.delenv("ASTERISM_INSPECT_DELIVERY_CHARS")
    mcp_tools.inspect([{"size": "."}])
    monkeypatch.setenv("ASTERISM_INSPECT_DELIVERY_CHARS", "junk")
    mcp_tools.inspect([{"size": "."}])
    assert seen == [30000, None, None]


def test_empty_capabilities_are_not_advertised() -> None:
    """Zero resources/prompts must mean the capability is ABSENT from
    initialize — FastMCP advertises them unconditionally and every
    codex intake burned its first calls discovering the emptiness
    (`list_mcp_resources` x23, feedback 2026-08-25). Both servers."""
    from mcp.server.lowlevel.server import NotificationOptions
    from Tooling.knowledge import mcp_tools
    caps = mcp_tools.mcp._mcp_server.get_capabilities(
        NotificationOptions(), {})
    assert caps.resources is None and caps.prompts is None
    assert caps.tools is not None


# ---------------------------------------------------------------------
# The Assistant's surface (HID §1.1 capability matrix, §3.5, §3.8)
# ---------------------------------------------------------------------


@pytest.fixture
def assistant_ws(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A workspace the tools resolve to, the way a spawn does: the
    Assistant's cwd IS the workspace (`serve/chat.py` passes it), and
    `workspace_of` walks up to the directory owning Problems+Tooling."""
    (tmp_path / "Problems").mkdir()
    (tmp_path / "Tooling").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _seed_project(workspace: Path, problem: str = "Erdos.p1") -> int:
    from Tooling.state import db
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    now = db.now()
    conn.execute("INSERT INTO projects (name, description, created_at)"
                 " VALUES ('Erdos', '', ?)", (now,))
    conn.execute("INSERT INTO problems (name, project, created_at)"
                 " VALUES (?, 'Erdos', ?)", (problem, now))
    conn.execute(
        "INSERT INTO goals (problem, slug, statement, status, kind,"
        " origin, depth, lean_path, created_at, updated_at)"
        " VALUES (?, 'deficit', 'theorem d : True', 'open', 'theorem',"
        " 'root', 0, 'proofs/d.lean', ?, ?)", (problem, now, now))
    gid = int(conn.execute("SELECT id FROM goals").fetchone()["id"])
    conn.commit()
    conn.close()
    return gid


def test_the_assistant_seat_is_declared_and_carries_no_act_channel(
) -> None:
    """§1.1's matrix as a table, not a comment.

    `compute` and `paper_fetch` joined the seat by owner ruling
    2026-09-02: §1.1 lists both as Assistant capabilities (`compute`, and
    找論文), and neither is an act channel — `compute` runs in the
    gateway's own sandbox with no filesystem, network or shell, and
    `paper_fetch` goes through `papers/fetch`, the intake chokepoint,
    not a raw DB write. What stays out is what would let the Assistant
    stand in for a worker: `write_file` (a worker's attempts dir, which
    the Assistant does not have) and `validate_json` (a worker's
    hand-in), plus every act channel there has never been."""
    from Tooling.llm.envelope import asterism_tools_for

    seat = asterism_tools_for("explainer")
    assert {"write_project_doc", "list_project_docs", "read_project_doc",
            "prepare_command", "daemon_status", "inspect",
            "compute", "paper_fetch"} <= seat
    for banned in ("write_file", "validate_json"):
        assert banned not in seat, banned


def test_write_project_doc_lands_under_agent(assistant_ws: Path) -> None:
    from Tooling.knowledge import mcp_tools
    from Tooling.state import project_docs

    out = mcp_tools.write_project_doc(
        project="Erdos", path="agent/summary.md", content="# what I read\n")
    assert "agent/summary.md" in out
    assert project_docs.read(assistant_ws, "Erdos", "agent/summary.md") \
        == b"# what I read\n"


def test_write_project_doc_refuses_the_persons_area(
    assistant_ws: Path,
) -> None:
    """The Assistant's whole write surface. A refusal that did not name
    `agent/` would be a refusal it routes around."""
    from Tooling.knowledge import mcp_tools

    out = mcp_tools.write_project_doc(
        project="Erdos", path="user/notes.md", content="x")
    assert "agent/notes.md" in out
    assert not (assistant_ws / "Problems" / "Erdos" / "_docs" / "user"
                ).exists()


def test_list_and_read_project_docs(assistant_ws: Path) -> None:
    from Tooling.knowledge import mcp_tools
    from Tooling.state import project_docs

    project_docs.write(assistant_ws, "Erdos", "user/plan.md", "the plan\n")
    listing = mcp_tools.list_project_docs(project="Erdos")
    assert "user/plan.md" in listing
    assert "the plan" in mcp_tools.read_project_doc(
        project="Erdos", path="user/plan.md")


def test_read_project_doc_names_the_way_out_when_it_misses(
    assistant_ws: Path,
) -> None:
    from Tooling.knowledge import mcp_tools

    out = mcp_tools.read_project_doc(project="Erdos", path="user/ghost.md")
    assert "list_project_docs" in out


def test_prepare_command_previews_and_never_enqueues(
    assistant_ws: Path,
) -> None:
    """§3.8: the Assistant PREPARES. The person presses the button, and
    that is not a policy the prompt enforces — no queue row exists after
    this call, on any path."""
    import sqlite3

    gid = _seed_project(assistant_ws)
    from Tooling.knowledge import mcp_tools

    out = json.loads(mcp_tools.prepare_command(
        problem="Erdos.p1", kind="ConfirmShelve",
        payload={"target_goal_id": gid, "reason": "the route is dead"}))
    assert out["kind"] == "ConfirmShelve"
    assert out["problem"] == "Erdos.p1"
    assert out["payload"]["target_goal_id"] == gid
    assert out["preview"]["affected"][0]["slug"] == "deficit"
    conn = sqlite3.connect(assistant_ws / "asterism.db")
    assert conn.execute(
        "SELECT COUNT(*) FROM human_commands").fetchone()[0] == 0
    conn.close()


def test_prepare_command_refuses_what_the_post_would_refuse(
    assistant_ws: Path,
) -> None:
    """One validator, two doors: a payload the POST would 422 must not
    be handed to the person as a ready command."""
    gid = _seed_project(assistant_ws)
    from Tooling.knowledge import mcp_tools

    out = mcp_tools.prepare_command(
        problem="Erdos.p1", kind="ConfirmShelve",
        payload={"target_goal_id": gid})
    assert "reason" in out and "preview" not in out


def test_prepare_command_refuses_an_unknown_kind(assistant_ws: Path) -> None:
    _seed_project(assistant_ws)
    from Tooling.knowledge import mcp_tools

    out = mcp_tools.prepare_command(problem="Erdos.p1", kind="DropTable",
                                    payload={})
    assert "ConfirmShelve" in out


def test_daemon_status_is_read_only(assistant_ws: Path) -> None:
    from Tooling.knowledge import mcp_tools

    out = json.loads(mcp_tools.daemon_status())
    assert out["running"] is False
