"""`_theorize.json` — the resume point of one theory request.

WHY IT EXISTS. 2026-09-06, union_closed g694: a Theorist wrote a
228k-token document, its reviewer died on the five-hour quota at 01:43Z,
and the infra re-dispatch (correct, `b4622245`) started a FRESH author
which rewrote the whole document from scratch — 223k tokens, on the same
wall, answering the same request. The author's work was thrown away by a
REVIEWER's transport death, and nothing in the framework could have
noticed: `run_theorist` held its entire state in local variables, so a
process that ended held nothing a successor could read.

WHAT IT IS. A single JSON file in the pipeline's attempts dir, rewritten
at every state change. It names the request, the wall, the author's
session and — the load-bearing part — the PHASE:

  `authoring`         the author is writing round k's document
  `awaiting_review`   round k's document is final; no ruling on it yet
  `awaiting_revision` round k's ruling fired; the author has not answered
  `landing`           the rounds are over; the document has not landed

THE FIELD IS NOT THE TRUTH; the dir is. The checkpoint is written BEFORE
the spawn it describes (a file written after a death is a file that does
not exist), so its phase is always one state ahead of what happened.
`resolve` reconciles: `review/r<k>/verdict.json` exists iff the reviewer
ruled, and the digest of the document the reviewer was HANDED tells a
revision that wrote something new from one that died before touching the
file. That second test is the same rule `run_theorist` already applies
inside one process (`body == reviewed`) — re-reviewing an unchanged
document spends a reviewer on a turn that never happened.

WHERE A RESUME LOOKS. `.attempts/*/` — a dir the sweeps now spare while
its decision is unanswered — and `.asterism/theory_frozen/*/`, where a
person parks a run they stopped by hand.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .review import PROJECTION_DIRNAME, projection_dir
from .verdict import (REPORT_BASENAME, VERDICT_BASENAME, parse_theory_verdict)

#: The file, and the one spelling of its name. `agent/runtime.py` cannot
#: import this module at module level (the pipeline package imports
#: `agent`), so it carries the string inline — held level by a test.
CHECKPOINT_BASENAME = "_theorize.json"

#: Where a person parks a run stopped by hand. Under `.asterism/`, which
#: no sweep walks, so a frozen run keeps until it is adopted.
FROZEN_DIRNAME = "theory_frozen"

PHASE_AUTHORING = "authoring"
PHASE_AWAITING_REVIEW = "awaiting_review"
PHASE_AWAITING_REVISION = "awaiting_revision"
PHASE_LANDING = "landing"

PHASES = (PHASE_AUTHORING, PHASE_AWAITING_REVIEW,
          PHASE_AWAITING_REVISION, PHASE_LANDING)

#: The rounds' objections, assembled for a FRESH author that could not
#: inherit the dead session. Its own file because the reviewer's
#: `dialogue.md` opens with an instruction addressed to a judge.
DIALOGUE_BASENAME = "dialogue.md"

#: The author prompt with the resume brief appended — the review round's
#: `_render_prompt` idiom: what varies per run is appended to the static
#: prompt, never written into it.
RESUME_PROMPT_BASENAME = "_theory_resume_prompt.md"

#: What does NOT travel from the old dir into the resumed pipeline's.
#: Each of these belongs to the process that wrote it: a carried
#: `_spawn.stderr` would name the OLD run's death when this one's seat
#: dies quietly, and a carried gateway token would release a slot this
#: pipeline never held. `Context.md` is recompiled for this run.
#: `_codex_sessions.json` is deliberately NOT here — it is the map from
#: the framework's session id to codex's thread, i.e. the only thing
#: that makes `exec resume` possible on that provider.
_CARRY_SKIP_FILES = frozenset({
    CHECKPOINT_BASENAME, "Context.md", "_spawn.stderr",
    "_parser_state.json", "_gateway_session.token", "_mcp_tools.json",
    "_context_stats.json",
})
_CARRY_SKIP_DIRS = frozenset({"sandbox"})


@dataclass(frozen=True)
class Resume:
    """A run picked up where it stopped."""
    source: Path
    source_pipeline_id: str
    phase: str
    round_no: int
    author_sid: str
    provider: str
    model: str
    started_at: str

    @property
    def author_is_resumable(self) -> bool:
        """A session id is only worth `--resume` when the seat is still
        on the provider that minted it — a sid is a claude session or a
        codex thread, never both."""
        from ...llm import capabilities as _caps
        return bool(self.author_sid) and (
            self.provider == _caps.provider_for_kind("theorist"))


def digest(body: str) -> str:
    """What identifies a document across processes. sha256 of the bytes,
    not the length: two revisions of one document differ by a paragraph
    far more often than by a byte count."""
    return hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()


def path_in(attempts_dir: Path) -> Path:
    return Path(attempts_dir) / CHECKPOINT_BASENAME


def write(attempts_dir: Path, *, decision_id: "int | None",
          group_id: "int | None", problem: str, author_sid: str,
          provider: str, model: str, phase: str, round_no: int,
          started_at: str, updated_at: "str | None" = None,
          reviewed_sha: str = "", resumed_from: str = "") -> Path:
    """Rewrite the checkpoint. Best-effort by nature — a run that cannot
    write its resume point still has to do the work in front of it — but
    LOUD, because a silent failure here is the incident again."""
    from ...state.db import now as _now
    data = {
        "decision_id": None if decision_id is None else int(decision_id),
        "group_id": None if group_id is None else int(group_id),
        "problem": problem,
        "author_sid": author_sid,
        "provider": provider,
        "model": model,
        "phase": phase,
        "round": int(round_no),
        "reviewed_sha": reviewed_sha,
        "resumed_from": resumed_from,
        "started_at": started_at,
        "updated_at": updated_at or _now(),
    }
    target = path_in(attempts_dir)
    try:
        target.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    except OSError as exc:
        print(f"[theorist] could not write {CHECKPOINT_BASENAME}: {exc} "
              f"— this run cannot be resumed", flush=True)
    return target


def load(attempts_dir: Path) -> "dict | None":
    try:
        data = json.loads(
            path_in(attempts_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def report_body(attempts_dir: Path) -> str:
    p = Path(attempts_dir) / REPORT_BASENAME
    try:
        return p.read_text(encoding="utf-8") if p.is_file() else ""
    except OSError:
        return ""


def verdict_at(attempts_dir: Path, round_no: int) -> "dict | None":
    """Round `round_no`'s ruling, parsed — or None when the reviewer
    never produced one. The file's EXISTENCE is the structured signal
    the resume branches on; a file the parser refuses is treated as no
    ruling, which is what the round itself does with it."""
    p = projection_dir(Path(attempts_dir), int(round_no)) / VERDICT_BASENAME
    try:
        raw = p.read_text(encoding="utf-8") if p.is_file() else ""
    except OSError:
        return None
    if not raw.strip():
        return None
    v, _err = parse_theory_verdict(raw)
    return v


def dialogue_upto(attempts_dir: Path, round_no: int) -> "list[dict]":
    """The rebuttals rounds 1..`round_no` produced, in the shape
    `review.build_review_projection` reads. Rebuilt from the verdict
    files rather than carried in the checkpoint: the files are the
    record, and a second copy is a second thing to keep true."""
    out: "list[dict]" = []
    for k in range(1, max(0, int(round_no)) + 1):
        v = verdict_at(attempts_dir, k)
        if v is not None and v.get("verdict") != "pass":
            out.append({"round": k, "criticisms": v.get("criticisms", [])})
    return out


def resolve(attempts_dir: Path, data: "dict | None"
            ) -> "tuple[str, int]":
    """(phase, round) as the DIR has it — see the module docstring."""
    data = data or {}
    phase = str(data.get("phase") or PHASE_AUTHORING)
    if phase not in PHASES:
        phase = PHASE_AUTHORING
    try:
        k = max(1, int(data.get("round") or 1))
    except (TypeError, ValueError):
        k = 1
    v = verdict_at(attempts_dir, k)
    if v is not None:
        return ((PHASE_LANDING if v.get("verdict") == "pass"
                 else PHASE_AWAITING_REVISION), k)
    if phase == PHASE_AUTHORING:
        body = report_body(attempts_dir)
        if body.strip() and digest(body) != str(
                data.get("reviewed_sha") or ""):
            # A draft caught mid-turn IS the submission: the prompt tells
            # the author to update `report.md` as it thinks.
            return PHASE_AWAITING_REVIEW, k
        if k > 1:
            # Round k-1 fired and this turn wrote nothing new — the
            # revision is still owed.
            return PHASE_AWAITING_REVISION, k - 1
        return PHASE_AUTHORING, 1
    return phase, k


_ROUND_DIR_RE = re.compile(r"^r(\d+)$")
#: A UUID as the claude CLI echoes the `--session-id` it was pinned to,
#: in its `init` event — which lands in `_spawn.stderr` on any spawn that
#: failed. The only place a dead run's author session survives on disk.
_SID_RE = re.compile(r'"session_id"\s*:\s*"([0-9a-fA-F-]{36})"')


def rounds_present(attempts_dir: Path) -> int:
    """The highest round this dir has a dossier for; 0 when none."""
    root = Path(attempts_dir) / PROJECTION_DIRNAME
    if not root.is_dir():
        return 0
    best = 0
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0
    for d in entries:
        m = _ROUND_DIR_RE.match(d.name)
        if d.is_dir() and m:
            best = max(best, int(m.group(1)))
    return best


def probe(attempts_dir: Path) -> "tuple[str, int]":
    """(phase, round) read off a dir that was never stamped.

    For the operator's adopt path: what a run reached is a property of
    the FILES it left, so a person may not declare a state the dir does
    not have."""
    k = rounds_present(attempts_dir)
    if k == 0:
        return ((PHASE_AWAITING_REVIEW
                 if report_body(attempts_dir).strip() else PHASE_AUTHORING),
                1)
    return resolve(attempts_dir,
                   {"phase": PHASE_AWAITING_REVIEW, "round": k})


def author_sid_in(attempts_dir: Path) -> str:
    """The framework session id the author ran under, as THIS dir
    records it — "" when the dir does not.

    Two shapes, because two providers write one. codex keeps the map
    from the framework's session id to its own thread
    (`_codex_sessions.json`, and its KEY is what a resume passes back);
    claude echoes the pinned `--session-id` in the init event its
    adapter captures into `_spawn.stderr` on a failed spawn. A dir whose
    last spawn exited 0 keeps neither — the sid is then in the
    provider's own transcript store (for claude,
    `~/.claude/projects/<munged problem dir>/<sid>.jsonl`, findable by
    grepping the pipeline id) and has to be passed in by hand."""
    d = Path(attempts_dir)
    try:
        m = json.loads((d / "_codex_sessions.json").read_text(
            encoding="utf-8"))
        if isinstance(m, dict) and len(m) == 1:
            return str(next(iter(m)))
    except (OSError, ValueError, StopIteration):
        pass
    try:
        text = (d / "_spawn.stderr").read_text(encoding="utf-8",
                                               errors="replace")
    except OSError:
        return ""
    hit = _SID_RE.search(text)
    return hit.group(1) if hit else ""


def search_roots(workspace: Path) -> "list[Path]":
    """Where a resumable run can be. `.attempts/` for a run whose
    process died, `.asterism/theory_frozen/` for one a person stopped."""
    ws = Path(workspace)
    return [ws / ".attempts", ws / ".asterism" / FROZEN_DIRNAME]


def find(workspace: Path, decision_id: "int | None", *,
         skip: str = "") -> "tuple[Path, dict] | None":
    """The NEWEST checkpoint for this decision, by its own clock.

    Newest, not first: a request can have been answered more than once,
    and the run that got furthest is the one worth picking up. `skip` is
    the caller's own pipeline id — a run must never adopt itself."""
    if decision_id is None:
        return None
    best: "tuple[str, float, Path, dict] | None" = None
    for root in search_roots(workspace):
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for d in entries:
            if not d.is_dir() or d.name == skip:
                continue
            data = load(d)
            if data is None or data.get("decision_id") is None:
                continue
            try:
                if int(data["decision_id"]) != int(decision_id):
                    continue
            except (TypeError, ValueError):
                continue
            try:
                mtime = path_in(d).stat().st_mtime
            except OSError:
                mtime = 0.0
            key = (str(data.get("updated_at") or ""), mtime, d, data)
            if best is None or key[:2] > best[:2]:
                best = key
    return (best[2], best[3]) if best is not None else None


def carry(src: Path, dst: Path) -> None:
    """Move the old run's record into THIS pipeline's attempts dir, so
    the standard layout holds from here on. Copy, not move: the frozen
    dir is the operator's evidence and outlives the run that adopts it."""
    dst.mkdir(parents=True, exist_ok=True)
    try:
        entries = sorted(Path(src).iterdir())
    except OSError as exc:
        print(f"[theorist] could not read {src}: {exc}", flush=True)
        return
    for item in entries:
        if item.is_dir():
            if item.name in _CARRY_SKIP_DIRS:
                continue
            shutil.copytree(item, dst / item.name, dirs_exist_ok=True)
        elif item.name not in _CARRY_SKIP_FILES:
            shutil.copy2(item, dst / item.name)


def adopt(workspace: Path, attempts_dir: Path, *,
          decision_id: "int | None", pipeline_id: str) -> "Resume | None":
    """Find the newest checkpoint for this request, copy its files in,
    and say where the run stands. None when there is nothing to resume."""
    found = find(Path(workspace), decision_id, skip=pipeline_id)
    if found is None:
        return None
    src, data = found
    carry(src, Path(attempts_dir))
    phase, round_no = resolve(Path(attempts_dir), data)
    return Resume(
        source=src, source_pipeline_id=src.name, phase=phase,
        round_no=round_no, author_sid=str(data.get("author_sid") or ""),
        provider=str(data.get("provider") or ""),
        model=str(data.get("model") or ""),
        started_at=str(data.get("started_at") or ""))


def write_dialogue(attempts_dir: Path, dialogue: "list[dict]") -> Path:
    """Every round's objections, for an author that has to be TOLD what
    its own earlier turns were answering."""
    out = ["# The review so far",
           "",
           "Earlier rounds of this review, in order. Your revision "
           "answers the LAST one; the others are settled unless the "
           "reviewer raised them again.",
           ""]
    for entry in dialogue:
        out.append(f"## round {entry.get('round', '?')} — reviewer")
        out += [f"- {c}" for c in entry.get("criticisms", [])]
        out.append("")
    p = Path(attempts_dir) / DIALOGUE_BASENAME
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def resume_prompt(attempts_dir: Path, base_prompt: Path, *,
                  round_no: int, criticisms: "list[str]") -> Path:
    """The author prompt plus what a FRESH session cannot know.

    Used when the recorded session cannot be replayed. Appended, not
    written into `prompts/theorist/theory.md`: which run this is and
    what was said to it varies per spawn, and a static prompt that
    described a resume would describe it on every cold wake too."""
    where = Path(attempts_dir).as_posix()
    ruling = "\n".join(f"- {c}" for c in criticisms) or "- (not recorded)"
    brief = (
        "\n\n## You are continuing an interrupted run\n\n"
        f"An earlier turn on THIS request already wrote `{where}/"
        f"{REPORT_BASENAME}` and put it to the reviewer {round_no} "
        f"time(s). That process is gone and its session cannot be "
        f"replayed, so what it was thinking is not available to you — "
        f"the files are.\n\n"
        f"- `{where}/{REPORT_BASENAME}` — the document as it stands. "
        f"REVISE it; do not start a new one.\n"
        f"- `{where}/{DIALOGUE_BASENAME}` — every earlier round's "
        f"objections.\n\n"
        f"The ruling this turn answers (round {round_no}):\n\n"
        f"{ruling}\n")
    dst = Path(attempts_dir) / RESUME_PROMPT_BASENAME
    dst.write_text(
        Path(base_prompt).read_text(encoding="utf-8") + brief,
        encoding="utf-8")
    return dst


def hand_to_author(attempts_dir: Path, resumed: Resume, *,
                   base_prompt: Path, verdict: "dict | None",
                   dialogue: "list[dict]", cold_sid: str,
                   label: str = "") -> "tuple[str, Path, bool]":
    """How the revision turn reaches an author. Returns
    (session id, prompt to send, must-run-cold); `cold_sid` is the fresh
    id to pin when the recorded one cannot be replayed.

    Its OWN session is the cheapest way back into the argument — the
    document, the objections and everything the author was thinking are
    already in it. When the seat has moved provider since, that id is a
    claude session being handed to codex or the reverse, so the turn
    runs cold instead; the prompt is then the only channel there is, and
    it carries the document, the dialogue and the ruling. That prompt is
    rendered EITHER WAY, because a provider can also fall back to cold
    on its own (codex does, silently, when its thread map is gone) and a
    cold turn holding only the static prompt would rewrite the document
    from nothing — the incident, one layer down."""
    write_dialogue(attempts_dir, dialogue)
    prompt = resume_prompt(
        attempts_dir, base_prompt, round_no=resumed.round_no,
        criticisms=(verdict or {}).get("criticisms", []))
    if resumed.author_is_resumable:
        return resumed.author_sid, prompt, False
    print(f"[theorist] {label}: the author's session cannot be resumed "
          f"(sid {resumed.author_sid or '(none recorded)'}, seat was on "
          f"{resumed.provider or '(unknown)'}) — a fresh author is "
          f"seeded with {REPORT_BASENAME}, {DIALOGUE_BASENAME} and the "
          f"ruling", flush=True)
    return cold_sid, prompt, True


def _outcome_is_null(conn: sqlite3.Connection, decision_id: int) -> bool:
    try:
        row = conn.execute(
            "SELECT outcome FROM strategist_decisions WHERE id = ?",
            (int(decision_id),)).fetchone()
    except sqlite3.Error:
        return True   # cannot tell → keep the evidence
    return row is not None and row[0] is None


def holds_an_unanswered_request(attempts_dir: Path, *,
                                conn: "sqlite3.Connection | None" = None,
                                workspace: "Path | None" = None) -> bool:
    """Does deleting this dir destroy work nothing else has a copy of?

    True iff it carries a checkpoint whose `Theorize` row is still
    unanswered — the state that means "the theory layer is working" on
    every other surface. Every caller is a CLEANUP path, so the answer
    errs toward preservation: a checkpoint we cannot adjudicate keeps
    its dir, and one whose row has settled does not.

    `conn` when the caller has one (recovery). Otherwise a read-only
    open of the workspace DB — `WorkArea.__exit__` runs on a worker
    thread with no connection of its own, and `connect()` would
    auto-migrate, which no cleanup path may do."""
    data = load(attempts_dir)
    if data is None or data.get("decision_id") is None:
        return False
    try:
        did = int(data["decision_id"])
    except (TypeError, ValueError):
        return False
    if conn is not None:
        return _outcome_is_null(conn, did)
    db_path = Path(workspace or ".") / "asterism.db"
    if not db_path.is_file():
        return True
    try:
        ro = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro",
                             uri=True, timeout=30)
    except sqlite3.Error:
        return True
    try:
        return _outcome_is_null(ro, did)
    finally:
        ro.close()
