"""WorkArea + LLM dispatch.

Context.md compilation lives in `Tooling.context`. This module holds
only the WorkArea sandbox lifecycle and the synchronous dispatch shim
into `Tooling.llm`. Callers needing `compile_context` or the
`_section_*` helpers import them from `Tooling.context` directly.
"""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from ..core import config
from .. import llm


WORKER_TIMEOUT_SEC = 900  # 15 min. Phase 2 LSP cantor_xi had 6
                          # spawns hit the prior 600s wall while making
                          # real progress (esp. measure-theory leaves
                          # like cantorxi_next_*_vol). 900s gives Sonnet
                          # room to finish; fewer-but-longer spawns
                          # paired with shelve_threshold=4 keeps total
                          # cost on stuck goals bounded.

# Postmortem spawn after a main-spawn timeout. Uses --resume so
# session memory is intact; agent writes a short state + blocker note
# (`_progress.md`) and exits. 120s was empirically too tight for
# Sonnet to write a usable note on dense root-level state; 180s gives
# ~50% more breathing room for the same pattern.
POSTMORTEM_TIMEOUT_SEC = 180


_PROMPT_COND_RE = re.compile(
    r"[ \t]*<!-- #if (\w+) -->[ \t]*\n(.*?)[ \t]*<!-- #endif -->[ \t]*\n?",
    re.DOTALL)


def render_prompt_template(text: str, *, is_postmortem: bool = False,
                           flags: "dict[str, bool] | None" = None) -> str:
    """Substitute prompt template placeholders against live config.

    Replacements:
      - `{timeout_min}` — per-spawn wall-clock (WORKER_TIMEOUT_SEC for
        body prompts, POSTMORTEM_TIMEOUT_SEC for postmortems).
      - `{interval_min}` — Strategist T1 routine cadence (minutes;
        `strategist.interval_min` config knob). Only the strategist
        prompts (`strategist/*.md`) use this placeholder today; the
        substitution is a no-op for other prompts.
      - `<!-- #if name -->…<!-- #endif -->` — conditional block (D8
        2026-07-24: fresh-problem wakes drop the not-yet-applicable
        paragraphs without wording changes). The block stays when
        `flags` is None or the name is absent (fail-open); it is
        dropped only on an explicit falsy flag. Marker lines are
        always stripped.
    """
    def _cond(m: "re.Match[str]") -> str:
        if flags is None or flags.get(m.group(1), True):
            return m.group(2)
        return ""
    text = _PROMPT_COND_RE.sub(_cond, text)
    timeout_sec = (POSTMORTEM_TIMEOUT_SEC if is_postmortem
                   else WORKER_TIMEOUT_SEC)
    interval_min = config.get(
        "strategist.interval_min", default=120.0,
        env_var="ASTERISM_STRATEGIST_INTERVAL_MIN", cast=float,
    )
    return (text
            .replace("{timeout_min}", str(timeout_sec // 60))
            .replace("{interval_min}", _format_minutes(interval_min)))


def _format_minutes(value: float) -> str:
    """Render a minutes value compactly: integer when whole, one
    decimal otherwise. Avoids '60.0' noise for the common default."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


class WorkArea:
    """Ephemeral working area for one pipeline run.

    Holds two paths under `.attempts/`:
      * `attempts` = `.attempts/<pid>/`         agent sandbox, Context.md, outputs
      * `backup`   = `.attempts/_backup_<pid>/` Backward's pre-write proofs/ snapshot

    Both are unconditionally rmtree'd on `__exit__` (best-effort). A worker
    that needs to consume `backup` (e.g. Backward restoring on lake fail)
    must `shutil.move` it before the context exits — `__exit__` only cleans
    whatever is still on disk.
    """
    def __init__(self, workspace: Path, pipeline_id: str):
        self.workspace = workspace
        self.pipeline_id = pipeline_id
        self.attempts = workspace / ".attempts" / pipeline_id
        self.backup = workspace / ".attempts" / f"_backup_{pipeline_id}"

    def __enter__(self) -> "WorkArea":
        self.attempts.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Release the gateway session before tearing down attempts/.
        # `_write_mcp_config` only releases the PREVIOUS retry's token
        # (when overwriting on a fresh retry), so the LAST token of
        # each pipeline (and the only token of single-shot pipelines)
        # would otherwise leak — gateway accumulates SessionMetadata
        # entries indefinitely. Best-effort: release_session swallows
        # urlopen errors, so a dead gateway / network blip won't block
        # the rmtree.
        token_file = self.attempts / "_gateway_session.token"
        if token_file.exists():
            try:
                token = token_file.read_text(encoding="utf-8").strip()
            except OSError:
                token = ""
            if token:
                from ..lsp import lifecycle as gateway_lifecycle
                gateway_lifecycle.release_session(token)
        for p in (self.attempts, self.backup):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        return False


def spawn_llm(*, kind: str, prompt_path: Path, problem_dir: Path,
              attempts_dir: Path,
              session_id: str | None = None,
              is_retry: bool = False,
              retry_context: str | None = None,
              retry_reason: str | None = None,
              is_postmortem: bool = False,
              continuation: bool = False,
              timeout_sec: int | None = None,
              mcp_config_path: Path | None = None,
              inline_prompt: str | None = None,
              timeout_sec_override: int | None = None,
              trap_check_sec_override: int | None = None,
              usage_workspace: Path | None = None,
              usage_problem: str | None = None,
              usage_pipeline_id: str | None = None,
              prompt_flags: "dict[str, bool] | None" = None) -> int:
    """Dispatch to the configured LLM provider for one agent invocation.

    Provider is resolved per-kind: `ASTERISM_<KIND>_PROVIDER` →
    `ASTERISM_LLM_PROVIDER` → 'claude'. Likewise the model string is
    looked up per-kind inside each provider. Returns the provider's
    rc (0 success, 124 timeout, 125 stale session, 126 quota
    exhausted, 127 missing dep, 128 stuck thinking, other = error).

    `session_id` / `is_retry` / `retry_context`: in-pipeline same-
    session retry. Pass a UUID + is_retry=False on first attempt;
    same UUID + is_retry=True + the prior lake error string in
    `retry_context` on subsequent attempts within the same pipeline
    (Phase 7 — sid is a local var owned by the retry helper, not
    persisted across pipeline calls).

    `is_postmortem`: set on the postmortem spawn after a main
    timeout. Provider uses `--resume <session_id>`, loads `prompt_path`
    verbatim (a short instruction asking the agent to dump state +
    blockers into `_progress.md`). `timeout_sec` defaults to
    `POSTMORTEM_TIMEOUT_SEC` (180s) for postmortem calls and
    `WORKER_TIMEOUT_SEC` (900s) otherwise.

    `inline_prompt`: 2026-05-10 — fresh-rescue stage 2 / stage 3
    inline prompt. Caller has minted a fresh `session_id` and copied
    the broken session's jsonl to `attempts_dir/_broken_session.jsonl`
    so the agent can Read it. Provider sends `inline_prompt` verbatim
    as `-p` (no template loading), uses `--session-id <session_id>`
    (cold), skips the watchdog (these are short rescue/postmortem
    replacements). Pair with `timeout_sec_override` (typically 180s)
    for tight budgets.

    `usage_workspace` / `usage_problem` / `usage_pipeline_id`: explicit
    spawn_usage attribution for callers whose dirs break the standard
    layout (`attempts_dir = <ws>/.attempts/<pid>`, `problem_dir` under
    Problems/). The Adversary spawns into a projection dir nested
    inside another pipeline's attempts dir — the derived workspace
    pointed at `.attempts/<pid>/` and every judge row was silently
    dropped (b6: ~0.5h of judge cost invisible, 2026-07-18).
    """
    if timeout_sec is None:
        if is_postmortem:
            timeout_sec = config.get(
                "dispatch.postmortem_timeout_sec",
                default=POSTMORTEM_TIMEOUT_SEC,
                env_var="ASTERISM_POSTMORTEM_TIMEOUT_SEC", cast=int,
            )
        else:
            timeout_sec = config.get(
                "dispatch.spawn_timeout_sec",
                default=WORKER_TIMEOUT_SEC,
                env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int,
            )
    if timeout_sec_override is not None:
        timeout_sec = timeout_sec_override
    import time as _time
    _t0 = _time.monotonic()
    _before = _artifact_snapshot(problem_dir, usage_workspace,
                                 usage_problem)
    rc = llm.get_provider(kind=kind).spawn(llm.LLMRequest(
        kind=kind,
        prompt_path=prompt_path,
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
        timeout_sec=timeout_sec,
        trap_check_sec=trap_check_sec_override,
        session_id=session_id,
        is_retry=is_retry,
        retry_context=retry_context,
        retry_reason=retry_reason,
        is_postmortem=is_postmortem,
        continuation=continuation,
        mcp_config_path=mcp_config_path,
        inline_prompt=inline_prompt,
        prompt_flags=prompt_flags,
    ))
    _record_spawn_usage(kind=kind, attempts_dir=attempts_dir,
                        problem_dir=problem_dir,
                        wall_sec=_time.monotonic() - _t0,
                        workspace=usage_workspace, problem=usage_problem,
                        pipeline_id=usage_pipeline_id)
    _artifact_audit(kind=kind, problem_dir=problem_dir,
                    workspace=usage_workspace, problem=usage_problem,
                    attempts_dir=attempts_dir, before=_before)
    return rc


#: The problem-dir files whose baseline is pinned (`user_file_history`
#: + the root gate). Watched here, enforced there.
_USER_FILES = ("Root.lean", "Defs.lean", "Manifest.md")

#: Repo regions where a write DURING a spawn is expected, so a change
#: there is not evidence of anything: the spawn sandboxes, the
#: framework's own runtime state, the Scholar's shelf, the harvest
#: target, and the benchmark ledger. `Problems/**/proofs/` needs no
#: entry — it is gitignored, hence invisible to `_repo_status`, and is
#: adjudicated by the per-lease footprint instead.
_EXPECTED_WRITE_PREFIXES = (
    ".attempts/", ".asterism/", "Papers/", "Library/", "Benchmarks/",
)

#: Where a violation is recorded, one JSON object per audit. A log line
#: only reaches whoever is watching the log — which is the operator and
#: nobody else. The durable record is what a future rollback would need
#: as input (user ruling 2026-07-30: shouting has limited value, the
#: risk is low, revisit with a real revert mechanism if it ever bites).
_AUDIT_LEDGER = ".asterism/artifact_audit.jsonl"


def _artifact_snapshot(problem_dir: Path, workspace: "Path | None",
                       problem: "str | None") -> dict:
    """One observation of everything the audit compares.

    Three questions, three instruments, because no single one answers
    all three (see `_artifact_audit` for what each layer is for)."""
    return {
        "user": _digests(problem_dir, _USER_FILES),
        "proofs": _digests(problem_dir / "proofs", None),
        "legit": _legit_proofs_writes(workspace, problem),
        "repo": _repo_status(workspace),
    }


def _digests(base: Path, names: "tuple[str, ...] | None") -> "dict[str, str]":
    """blake2b of `names` under `base`, or of every `*.lean` when None.

    Hashes rather than mtimes: a rewrite with identical bytes is not a
    change worth reporting, and mtime alone fires on tools that touch
    without writing."""
    import hashlib
    out: "dict[str, str]" = {}
    try:
        files = ([base / n for n in names] if names
                 else sorted(base.glob("*.lean")))
    except OSError:
        return out
    for f in files:
        try:
            out[f.name] = hashlib.blake2b(f.read_bytes(),
                                          digest_size=8).hexdigest()
        except OSError:
            pass
    return out


def _repo_status(workspace: "Path | None") -> "set[str]":
    """`git status --porcelain -uall`, as a line set.

    The cheap way to ask "what in this repo is not as committed?"
    without enumerating a guarded list — and enumerations rot: the old
    check watched three files plus one `proofs/` dir, so a spawn writing
    into `Tooling/`, another problem, `lakefile.lean` or `Asterism.yaml`
    was entirely unwatched. ~100ms measured on this repo (23 lines).

    Two blind spots, stated rather than papered over. A MODIFICATION to
    an untracked file yields no new line (its `??` line is already
    there), which is exactly the case for every user file of a problem
    that was never committed — hence the separate digests. And ignored
    trees are invisible, which is why `proofs/` is a different layer."""
    if workspace is None:
        return set()
    import subprocess

    from ..core.process_group import no_window_creationflags
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=str(workspace), capture_output=True, text=True,
            timeout=30, creationflags=no_window_creationflags())
    except Exception:  # noqa: BLE001 — not a repo / git missing / slow disk
        return set()
    if r.returncode != 0:
        return set()
    return {ln for ln in r.stdout.splitlines() if ln.strip()}


#: `_legit_proofs_writes` sentinel: every `proofs/` path is fair game
#: this round. Widening beats failing — see the docstring.
_PROOFS_ALL = "*"


def _legit_proofs_writes(workspace: "Path | None",
                         problem: "str | None") -> "set[str] | str":
    """The `proofs/` files that in-flight work may legitimately change.

    "Who wrote this file" has no answer from file snapshots: with
    `dispatch.pool` > 1 the framework commits a sibling pipeline's work
    through `state/proof_store` while this spawn runs, and on 2026-07-30
    a decomposition legitimately rewrote its target's own file into an
    alias — which the previous check called tampering and used to
    discard an honest spawn's output.

    "Does ANY live lease have business touching this file" does have an
    answer, and the queue holds it. A Goal-targeted worker may change
    its goal's file and its strategies' files; a Problem-targeted one
    (mint, Librarian, harvest) sweeps the tree, so the honest answer for
    it is "all of it".

    Unknown lease kinds and unresolvable state WIDEN rather than
    narrow. That direction is the whole lesson of the 07-30 misfire: a
    model of legitimacy that is incomplete must be loud, never fatal,
    or it spends its life failing honest work."""
    if workspace is None or not problem:
        return _PROOFS_ALL
    from ..state import db as _db
    allowed: "set[str]" = set()
    try:
        conn = _db.connect(workspace / "asterism.db")
    except Exception:  # noqa: BLE001 — no DB (unit-test spawn, fresh tree)
        return _PROOFS_ALL
    try:
        leases = conn.execute(
            "SELECT target_id, target_kind FROM queue"
            " WHERE owner_pid IS NOT NULL AND problem = ?",
            (problem,)).fetchall()
        for tid, tkind in leases:
            if tkind != "Goal" or not str(tid).isdigit():
                return _PROOFS_ALL
            for (lp,) in conn.execute(
                    "SELECT lean_path FROM goals WHERE id = ?", (tid,)):
                if lp:
                    allowed.add(Path(str(lp)).name)
            for lp, sp in conn.execute(
                    "SELECT lean_path, scratch_path FROM strategies"
                    " WHERE goal_id = ?", (tid,)):
                for p in (lp, sp):
                    if p:
                        allowed.add(Path(str(p)).name)
    except Exception:  # noqa: BLE001 — schema drift must not fail a spawn
        return _PROOFS_ALL
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return allowed


def _artifact_audit(*, kind: str, problem_dir: Path,
                    workspace: "Path | None", problem: "str | None",
                    attempts_dir: Path, before: dict) -> "list[dict]":
    """Report every write this spawn's window cannot account for.

    Replaces the sandbox rather than supplementing it (2026-07-30): the
    claude side denies the write tools and fences Bash with
    `ASTERISM_SPAWN_WRITE_ROOTS`, but the Antigravity side must run with
    `command(*)` — its permission matcher takes an exact literal or `*`
    and nothing between — and every command shells through powershell,
    so a write channel there is unavoidable. Checking afterwards catches
    a write through ANY channel: tool, shell, interpreter, MCP.

    Three layers, because each answers a question the others cannot:
      user files — no legitimate writer exists during a spawn, and the
        pin (`user_file_history` + root gate) is what enforces it;
      proofs/    — legitimacy is per-lease, not per-file (see
        `_legit_proofs_writes`); gitignored, so git cannot see it;
      the rest of the repo — the complement of the framework's own
        output regions, via `git status`; catches `Tooling/`, other
        problems, `lakefile.lean`, `Asterism.yaml`, which nothing
        watched before.

    NOT a soundness mechanism, and no layer fails the spawn. A written
    proof still faces the commit chokepoint, the per-decl axiom gate and
    the baseline pin; those decide. This layer turns "the fence held"
    from an assumption into an observation, and records enough for a
    revert to be written later without redoing the detection."""
    after = _artifact_snapshot(problem_dir, workspace, problem)
    out: "list[dict]" = []

    for name, was in sorted(before["user"].items()):
        if after["user"].get(name) != was:
            out.append({"layer": "user_file", "path": name,
                        "why": "the pinned baseline has no writer while "
                               "a spawn runs"})

    widened = _PROOFS_ALL in (before["legit"], after["legit"])
    if not widened:
        # Union of the lease snapshots taken either side of the spawn: a
        # lease released moments before the audit still legitimises the
        # write it just made. Narrowing to "live right now" would
        # reintroduce the same race in a new place.
        allowed = set(before["legit"]) | set(after["legit"])
        for name in sorted(set(before["proofs"]) | set(after["proofs"])):
            if (before["proofs"].get(name) != after["proofs"].get(name)
                    and name not in allowed):
                out.append({"layer": "proofs", "path": f"proofs/{name}",
                            "why": "no in-flight lease covers this file"})

    appeared = after["repo"] - before["repo"]
    for line in sorted(appeared):
        rel = line[3:].strip().strip('"')
        if rel.startswith(_EXPECTED_WRITE_PREFIXES):
            continue
        out.append({"layer": "repo", "path": rel,
                    "why": "outside every expected write region"})

    if not out:
        return out
    shown = ", ".join(v["path"] for v in out[:6])
    print(f"[artifact-audit] {kind} spawn: {len(out)} unaccounted write(s)"
          f" — {shown}{' …' if len(out) > 6 else ''}. Not failing the "
          f"spawn; the commit chokepoint, axiom gate and baseline pin "
          f"decide. Recorded in {_AUDIT_LEDGER}.", flush=True)
    _record_audit(workspace, kind=kind, problem=problem,
                  attempts_dir=attempts_dir, violations=out)
    return out


def _record_audit(workspace: "Path | None", *, kind: str,
                  problem: "str | None", attempts_dir: Path,
                  violations: "list[dict]") -> None:
    """Append the audit to the durable ledger. Best-effort: telemetry
    must never be the reason a spawn fails."""
    if workspace is None:
        return
    import json as _json
    from datetime import datetime, timezone
    try:
        path = workspace / _AUDIT_LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(timezone.utc).isoformat(),
               "kind": kind, "problem": problem,
               "attempts_dir": attempts_dir.name,
               "violations": violations}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _record_spawn_usage(*, kind: str, attempts_dir: Path,
                        problem_dir: Path, wall_sec: float,
                        workspace: Path | None = None,
                        problem: str | None = None,
                        pipeline_id: str | None = None) -> None:
    """Persist the spawn's token/turn accounting into `spawn_usage`
    (frontend charter §5-2). Source = the provider's
    `_parser_state.json` usage block (claude provider writes it; other
    providers simply have no file → no row). Best-effort throughout:
    telemetry must never fail a spawn. Own short-lived WAL connection —
    spawn_llm has no caller conn, and a per-spawn single INSERT is
    negligible contention."""
    import json as _json
    try:
        state_path = attempts_dir / "_parser_state.json"
        # Stale-file guard (review 07-27): early-return spawns (shutdown,
        # missing CLI, postmortem/inline paths) never rewrite this file,
        # so a PRIOR spawn's usage would be INSERTed a second time under
        # this spawn's wall time. The file must be younger than this
        # spawn (wall_sec is the spawn's duration; small clock-skew slack).
        import time as _time
        if state_path.stat().st_mtime < _time.time() - wall_sec - 30:
            return
        raw = state_path.read_text(encoding="utf-8")
        usage = (_json.loads(raw).get("usage") or {})
        if not (usage.get("turns") or usage.get("output_tokens")):
            return
        # Defaults assume the standard layout (explicit params override:
        # attempts_dir = <workspace>/.attempts/<pipeline_id>;
        # problem name = problem_dir relative to <workspace>/Problems
        # with / → . (matches db.problem_dir's inverse)).
        if workspace is None:
            workspace = attempts_dir.parent.parent
        if problem is None:
            try:
                rel = problem_dir.resolve().relative_to(
                    (workspace / "Problems").resolve())
                problem = ".".join(rel.parts)
            except ValueError:
                problem = problem_dir.name
        if pipeline_id is None:
            pipeline_id = attempts_dir.name
        from ..state import db as _db
        db_path = workspace / "asterism.db"
        if not db_path.exists():
            # A miscomputed workspace must fail silent-and-clean, not
            # mint a junk sqlite file wherever it happened to point.
            return
        vals = (int(usage.get("input_tokens") or 0),
                int(usage.get("output_tokens") or 0),
                int(usage.get("cache_read_input_tokens") or 0),
                int(usage.get("cache_creation_input_tokens") or 0),
                int(usage.get("turns") or 0))
        conn = _db.connect(db_path)
        try:
            # Exact-snapshot dedup (#126): the usage block is the
            # SESSION-CUMULATIVE snapshot, and tail hooks (feedback /
            # reflection resumes) re-enter this recorder with the same
            # numbers under their own kind label — 51% of historical
            # rows were byte-identical five-tuples, doubling every
            # SUM-based cost report. The first record (the work turn,
            # true kind + true wall time) wins; kind is deliberately
            # NOT part of the match.
            if conn.execute(
                "SELECT 1 FROM spawn_usage WHERE pipeline_id = ?"
                " AND input_tokens = ? AND output_tokens = ?"
                " AND cache_read_tokens = ? AND cache_new_tokens = ?"
                " AND turns = ? LIMIT 1",
                (pipeline_id, *vals)).fetchone() is not None:
                return
            conn.execute(
                "INSERT INTO spawn_usage (pipeline_id, kind, problem,"
                " input_tokens, output_tokens, cache_read_tokens,"
                " cache_new_tokens, turns, wall_sec, ts)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pipeline_id, kind, problem, *vals,
                 float(wall_sec), _db.now()))
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — telemetry never fails a spawn
        pass


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d
