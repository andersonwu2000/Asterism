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

#: The instruction, verbatim from the retired harness. Bare force: the
#: complete file back, signature untouched, nothing but Lean.
PROMPT = (
    "You are a Lean 4 / Mathlib expert. Below is a Lean file whose one "
    "theorem has its proof replaced by `sorry`. Write the complete file "
    "with a full working proof (Lean 4, current Mathlib). Keep imports, "
    "namespace, and the theorem signature EXACTLY as given. Do not add "
    "axioms, `sorry`, or `admit`. Reply with ONLY the complete Lean "
    "file, no markdown fences, no commentary.\n\n")

#: Where the answer is expected. The old harness read the provider's
#: message text; a framework seat writes files, so it is asked for one.
ANSWER_BASENAME = "answer.lean"

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
    with nothing but the stub."""
    from Tooling import agent
    from Tooling.agent import runtime as _rt
    from Tooling.state import db

    pid = str(uuid.uuid4())
    attempts = _rt.attempts_dir_for(Path(workspace), pid)
    attempts.mkdir(parents=True, exist_ok=True)
    prompt = attempts / "gauntlet_prompt.md"
    prompt.write_text(
        PROMPT + brick.stub
        + f"\n\nWrite the complete file to `{ANSWER_BASENAME}` in your "
          f"working directory.\n", encoding="utf-8")
    t0 = time.monotonic()
    rc = agent.spawn_llm(kind="formalizer", prompt_path=prompt,
                         problem_dir=db.problem_dir(Path(workspace), problem),
                         attempts_dir=attempts, session_id=str(uuid.uuid4()),
                         mcp_config_path=None,
                         usage_workspace=Path(workspace),
                         usage_problem=problem, usage_pipeline_id=pid)
    answer = attempts / ANSWER_BASENAME
    text = answer.read_text(encoding="utf-8", errors="replace") \
        if answer.is_file() else ""
    if not text:
        for cand in sorted(attempts.glob("*.lean")):
            if cand.name != prompt.name:
                text = cand.read_text(encoding="utf-8", errors="replace")
                break
    return text, {"pipeline_id": pid, "rc": rc,
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
