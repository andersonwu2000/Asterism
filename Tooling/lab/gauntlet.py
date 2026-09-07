"""The gauntlet — N independent Lean bricks, one shot each, no tools.

Ported from `.asterism/gauntlet/harness.py` (owner order 2026-08-27),
whose SEMANTICS are kept whole and whose paths are gone:

  * a brick is a file with EXACTLY ONE `theorem`/`lemma` — the old
    harness dropped multi-decl files because a second decl gives the
    candidate a proof to copy from.
  * the exam face is the file with its proof replaced by `sorry`: the
    head up to the first `:=` verbatim (so the signature is EXACTLY as
    given), then `:= by sorry`, then the file's trailing `end` lines.
  * one shot per brick. No tools, no gateway, no retry-on-error: the
    measurement is what the model can do with nothing.
  * a candidate carrying `sorry`, `admit` or an `axiom` is rejected
    BEFORE the compiler — it would otherwise compile and score.
  * the verdict is `lake env lean` on the candidate file, in the
    workspace, with that workspace's own toolchain.

WHAT IS GONE, and why each was ad-hoc: the brick SELECTION (a query
against the live `asterism.db` for proved `union_closed` theorems, then
a size/name/API spread) — a gauntlet whose exam set is recomputed from
a moving board measures a different exam every run, and it read the
live DB, which the lab may not do; and the six hardcoded provider legs
(an ssh hop to a named flagship, three curl recipes, a key file under
`Downloads/`) — a lab arm's seat is the workspace's own config, which
is the thing `run_record.json` can attest to.

So the bricks are INPUT now: `<root>/sets/gauntlet/bricks/*.lean`,
versioned with the set. With none there, the kind refuses and names
what it needs — inventing a set is the failure this port exists to
remove.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from . import LabError

#: The instruction, the retired harness's bare force with ONE sentence
#: changed: the answer comes back in the message, in a fence. The old
#: wording ("no markdown fences") was written for a raw API leg whose
#: whole response was the answer; a CLI seat prefixes and suffixes prose
#: whatever it is told, and `extract_lean` wants a fence to cut on.
PROMPT = (
    "You are a Lean 4 / Mathlib expert. Below is a Lean file whose one "
    "theorem has its proof replaced by `sorry`. Write the complete file "
    "with a full working proof (Lean 4, current Mathlib). Keep imports, "
    "namespace, and the theorem signature EXACTLY as given. Do not add "
    "axioms, `sorry`, or `admit`. Reply with the complete Lean file in "
    "ONE ```lean fence and nothing else — no commentary.\n\n")

#: Where a file answer is expected, when the seat can write one at all.
#: The seat is spawned with `mcp_config_path=None`, so it has NO
#: `write_file` / `apply_edit`, and on a codex backend no native file
#: tool either — the whole answer arrives as message text. So the file
#: is an OPTION, never the only channel: asking a seat with no file tool
#: for a file is how 7/7 answered bricks scored `REJECTED: empty` on
#: 2026-09-07 while every one of them held a complete Lean file in its
#: last message.
ANSWER_BASENAME = "answer.lean"

#: Where each provider preserves the spawn's transcript, relative to the
#: workspace (`llm.base.transcript_dest`). The message answer is read
#: back out of it — the spawn API returns an rc, not the prose.
TRANSCRIPT_LEAVES = ("codex_sessions", "agy_sessions")

_DECL_RE = re.compile(r"^(?:theorem|lemma)\s", re.M)
_HEAD_RE = re.compile(r"^((?:@\[[^\]]*\]\s*)?(?:theorem|lemma)\s[\s\S]*?):=",
                      re.M)
_BANNED_RE = re.compile(r"\bsorry\b|\badmit\b|^axiom\s", re.M)
_FENCE_RE = re.compile(r"```(?:lean4?|lean)?\s*\n([\s\S]*?)```")

#: How long one brick's compile may take. The old harness's number.
COMPILE_TIMEOUT_SEC = 900


@dataclass(frozen=True)
class Brick:
    slug: str
    path: Path
    stub: str


def _tail_end(text: str) -> str:
    ends = [ln for ln in text.splitlines() if ln.startswith("end ")]
    return ("\n".join(ends) + "\n") if ends else ""


def make_stub(text: str) -> "str | None":
    """The brick's exam face, or None when the decl will not split."""
    m = _HEAD_RE.search(text)
    if m is None:
        return None
    return text[:m.end(1)] + ":= by\n  sorry\n\n" + _tail_end(text)


def load_bricks(items_dir: Path) -> "list[Brick]":
    """Every `*.lean` under `items_dir` that is a single-decl brick."""
    items_dir = Path(items_dir)
    files = sorted(items_dir.glob("*.lean")) if items_dir.is_dir() else []
    bricks: "list[Brick]" = []
    skipped: "list[str]" = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        if len(_DECL_RE.findall(text)) != 1:
            skipped.append(f"{p.name} (not exactly one theorem/lemma)")
            continue
        stub = make_stub(text) if "sorry" not in text else text
        if stub is None:
            skipped.append(f"{p.name} (no `:=` to split the decl at)")
            continue
        bricks.append(Brick(slug=p.stem, path=p, stub=stub))
    if not bricks:
        raise LabError(
            f"the gauntlet has no bricks: {items_dir} holds no single-decl "
            f"Lean file"
            + (f" ({len(files)} .lean file(s) skipped: "
               f"{', '.join(skipped)})" if skipped else "")
            + ". Put one `*.lean` per brick there — a whole file with its "
              "imports, its namespace and EXACTLY ONE `theorem`/`lemma`, "
              "proof included (it is stripped to `sorry` here) or already "
              "stubbed. The retired harness picked its ten by querying "
              "the live DB for proved `Combinatorics.union_closed` "
              "theorems under `proofs/L_*` and spreading them over four "
              "buckets (4 leaf <1500 chars, 3 medium <4000, 2 census, 1 "
              "Mathlib-API); that selection is what this port drops, "
              "because a set recomputed from a moving board is a "
              "different exam every run.")
    for line in skipped:
        print(f"[gauntlet] skipped {line}", flush=True)
    return bricks


def reject(code: str) -> str:
    """Why this candidate must not reach the compiler, or ""."""
    if not code.strip():
        return "empty"
    if "theorem" not in code and "lemma" not in code:
        return "no-decl"
    if _BANNED_RE.search(code):
        return "sorry/axiom"
    return ""


def extract_lean(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else text


def _message_text(obj: object) -> str:
    """The assistant prose on one transcript line, or "".

    Tolerant by design, because the line shapes differ per provider and
    a shape this does not know must cost nothing: a codex rollout wraps
    everything in `payload` and says the last message twice (the
    `task_complete` event's `last_agent_message`, and the assistant
    `message` response item); a plain `{role, content}` jsonl says it
    once. Anything else yields "" and the scan moves on.
    """
    if not isinstance(obj, dict):
        return ""
    payload = obj.get("payload")
    payload = payload if isinstance(payload, dict) else obj
    if payload.get("type") == "task_complete":
        last = payload.get("last_agent_message")
        return last.strip() if isinstance(last, str) else ""
    if payload.get("role") != "assistant":
        return ""
    content = payload.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(c["text"] for c in content
                         if isinstance(c, dict)
                         and isinstance(c.get("text"), str)).strip()
    return ""


def final_message(attempts: Path) -> str:
    """The seat's LAST message, out of the transcript its provider
    preserved for this spawn, or "".

    `spawn_llm` returns an rc — the prose is not in its return value and
    the stream parser keeps state, not text. What every adapter DOES
    keep is the transcript, copied out of the doomed per-spawn home into
    `<ws>/.asterism/<leaf>/<pipeline id>/` before the home dies, and
    that is what is read here. A claude seat needs none of this: it has
    a native `Write` and answers with the file.
    """
    from ..llm.base import transcript_dest
    files: "list[Path]" = []
    for leaf in TRANSCRIPT_LEAVES:
        dest = transcript_dest(attempts, leaf)
        if dest is not None and dest.is_dir():
            files.extend(dest.rglob("*.jsonl"))
    text = ""
    for path in sorted(files, key=lambda p: p.stat().st_mtime):
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    said = _message_text(obj)
                    if said:
                        text = said
        except OSError as exc:
            print(f"[gauntlet] transcript {path.name} unreadable: {exc}",
                  flush=True)
    return text


def collect_answer(attempts: Path) -> "tuple[str, str]":
    """This spawn's answer and WHERE it came from: `file` when the seat
    wrote one with content, else `message`, else `none`.

    The file wins when both exist — a seat that can write a file has
    committed to it, and its message is then commentary about the file.
    """
    answer = attempts / ANSWER_BASENAME
    for path in ([answer] if answer.is_file() else []) + [
            p for p in sorted(attempts.glob("*.lean")) if p != answer]:
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.strip():
            return text, "file"
    text = final_message(attempts)
    return (text, "message") if text.strip() else ("", "none")


def lake_ok(workspace: Path, path: Path,
            timeout: int = COMPILE_TIMEOUT_SEC) -> "tuple[bool, str]":
    """`lake env lean <file>` in the workspace — the same verdict the
    old harness took, on the workspace's own toolchain."""
    try:
        r = subprocess.run(["lake", "env", "lean", str(path)],
                           cwd=str(workspace), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or ""))[-400:]
    except subprocess.TimeoutExpired:
        return False, "compile timeout"
    except (OSError, FileNotFoundError):
        return False, "lake not found"


def _spawn_once(workspace: Path, problem: str, brick: Brick,
                out: Path) -> "tuple[str, dict]":
    """One bare-force turn on this workspace's formalizer seat.

    `mcp_config_path=None` is the whole point: no gateway session, no
    `asterism_tools` — the gauntlet measures what the model produces
    with nothing but the stub. Which is also why the answer cannot be
    demanded as a file: that same flag takes `write_file` away, and a
    codex seat has no native one to fall back on. The prompt asks for
    the fence and offers the file; `collect_answer` takes either."""
    from Tooling import agent
    from Tooling.agent import runtime as _rt
    from Tooling.state import db

    pid = str(uuid.uuid4())
    attempts = _rt.attempts_dir_for(Path(workspace), pid)
    attempts.mkdir(parents=True, exist_ok=True)
    prompt = attempts / "gauntlet_prompt.md"
    prompt.write_text(
        PROMPT + brick.stub
        # ABSOLUTE, because cwd is the PROBLEM dir: a bare basename
        # lands outside the only directory this spawn may write, and
        # nothing would ever read it back (`render_prompt_template`'s
        # `{attempts_dir}` exists for the same reason).
        + f"\n\nIf you have a file-writing tool, also write the complete "
          f"file to `{(attempts / ANSWER_BASENAME).as_posix()}`. If you "
          f"do not, the fenced reply is the whole answer.\n",
        encoding="utf-8")
    t0 = time.monotonic()
    rc = agent.spawn_llm(kind="formalizer", prompt_path=prompt,
                         problem_dir=db.problem_dir(Path(workspace), problem),
                         attempts_dir=attempts, session_id=str(uuid.uuid4()),
                         mcp_config_path=None,
                         usage_workspace=Path(workspace),
                         usage_problem=problem, usage_pipeline_id=pid)
    text, source = collect_answer(attempts)
    return text, {"pipeline_id": pid, "rc": rc, "answer_source": source,
                  "gen_sec": round(time.monotonic() - t0, 1)}


def run(items_dir: Path, ws: Path, out: Path, *, problem: str,
        generate=None) -> dict:
    """Every brick, one shot each. `generate` is the turn — injectable
    so the harness's own logic is testable without a provider."""
    generate = generate or _spawn_once
    bricks = load_bricks(items_dir)
    work = Path(out) / "gauntlet"
    work.mkdir(parents=True, exist_ok=True)
    rows: "list[dict]" = []
    for brick in bricks:
        (work / f"{brick.slug}.stub.lean").write_text(brick.stub,
                                                      encoding="utf-8")
        text, meta = generate(Path(ws), problem, brick, Path(out))
        code = extract_lean(text).strip() + "\n"
        cand = work / f"{brick.slug}.lean"
        cand.write_text(code, encoding="utf-8")
        why = reject(code)
        if why:
            rows.append({"slug": brick.slug, "ok": False, "why": why, **meta})
        else:
            t0 = time.monotonic()
            ok, msg = lake_ok(Path(ws), cand)
            rows.append({"slug": brick.slug, "ok": ok,
                         "why": "" if ok else msg,
                         "compile_sec": round(time.monotonic() - t0, 1),
                         **meta})
        print(f"[gauntlet] {brick.slug}: "
              f"{'PROVED' if rows[-1]['ok'] else 'FAIL'} "
              f"[{rows[-1].get('answer_source', '?')}] "
              f"{rows[-1].get('why', '')[:120]}", flush=True)
    passed = sum(1 for r in rows if r["ok"])
    (work / "results.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[gauntlet] {passed}/{len(rows)}", flush=True)
    return {"outcome": "success" if rows else "failed", "bricks": rows,
            "bricks_passed": passed, "bricks_total": len(rows),
            "prompt_sha256": _sha(PROMPT),
            "pipeline_ids": [r["pipeline_id"] for r in rows
                             if r.get("pipeline_id")],
            "artefacts": ["gauntlet"]}


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
