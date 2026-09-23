"""The direct-session experiment: one agent, one theorem, three surfaces.

The question is what the framework's Lean surface COSTS the agent that
uses it, measured against the same agent given nothing but a shell. One
problem, one seat, three arms, N repetitions each:

  lsp    the gateway's MCP tools (`apply_edit`, `errors_at`, `goal_at`,
         `validate_file`) and nothing else — no shell, one file, as many
         declarations in it as the agent likes, and the gateway session
         registered as `direct` so the commit-time submission mirrors
         stay off (`lsp.gateway.state.DIRECT_KIND`).
  prod   the same tools under the PRODUCTION contract (kind `Backward`):
         mirrors on, one declaration per file, auxiliary lemmas as
         `new_<slug>.lean` stubs beside `patch.lean`.
  shell  no gateway at all — Bash, restricted to `lake env lean *`.

The problem is a folder, not a DB row: `Problems/<p>/` exists with its
`Defs.lean` built, and it is deliberately NOT `asterism init`ed. Nothing
here registers a goal, opens a strategy or commits anything; the only
row this module's work leaves behind is the `spawn_usage` one that
`spawn_llm` writes for itself, which is also the one it reads back.

THE VERDICT IS TAKEN COLD, operator-side, and never from the gateway: the
arm under measurement must not be the witness to its own result. The
assembled file is compiled by `lake env lean` with a `#print axioms`
appended, and `proved` means rc 0, no sorry warning, and an axiom set
inside `{propext, Classical.choice, Quot.sound}`. `false_green` — the
gateway said ok and the cold check disagrees — is a measurement of the
arm, not a bug in the run.

Run it one arm at a time:

    python -m Tooling.lab.direct_session --problem Combinatorics.single_root_direct \\
        --paper Problems/Combinatorics/_docs/user/uc_single_root_boundary_injection_2026-09-09.md \\
        --arm lsp --reps 2 --model claude-opus-5-5 --timeout-sec 3600 \\
        --out <runs dir> [--dry-run] [--workspace D:/Asterism]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

#: The axioms a finished Lean proof is allowed to stand on. Anything
#: else — `sorryAx` above all — means the file compiled without being a
#: proof, which is the failure mode this whole comparison is about.
PROOF_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

#: The three surfaces under comparison.
ARMS = ("lsp", "prod", "shell")

#: The `shell` arm's whole world. One pattern, no trailing free-form
#: command: the agent checks its own file and can do nothing else.
SHELL_ALLOW = ("Bash(lake env lean *)",)

#: Wall for ONE cold `lake env lean` verdict.
LAKE_TIMEOUT_SEC = 600

#: What the paper calls the problem. The Lean namespace here is the
#: problem slug's, and the two names have to be reconciled IN the prompt
#: or the agent reads the paper as being about something else.
PAPER_PROBLEM_NAME = "single_root_average_rare"


# ─── verdict primitives (pure) ───────────────────────────────────────

def normalise_ws(text: str) -> str:
    """Collapse every whitespace run to one space, ends trimmed."""
    return " ".join((text or "").split())


def _top_level_colon(text: str, start: int, stop: int) -> int:
    """Index of the first `:` between `start` and `stop` that is at
    paren/brace/bracket depth zero and is not the head of a `:=`; -1 if
    there is none. Depth-walked for the same reason
    `assemble.body_assign_index` is: a binder's own `:` sits inside
    parentheses and is not the signature's."""
    depth = 0
    pos = start
    while pos < stop:
        ch = text[pos]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == ":" and text[pos + 1:pos + 2] != "=":
            return pos
        pos += 1
    return -1


def main_statement(text: str, *, name: str = "main") -> "str | None":
    """The statement of `theorem <name>` in `text` — everything from its
    top-level `:` up to the body's `:=` — with whitespace normalised.
    None when the declaration is absent or has no body.

    This is the fidelity check: an agent that could not prove the
    theorem as given can always prove a weaker one, and a weakened
    hypothesis is invisible in `lake` rc 0."""
    from ..state import assemble
    m = re.search(r"\b(?:theorem|lemma)\s+" + re.escape(name) + r"\b",
                  text or "")
    if m is None:
        return None
    end = assemble.body_assign_index(text, m.end())
    if end < 0:
        return None
    colon = _top_level_colon(text, m.end(), end)
    if colon < 0:
        return None
    return normalise_ws(text[colon + 1:end])


def statements_identical(a: str, b: str, *, name: str = "main") -> bool:
    """Whether both texts state `theorem <name>` the same way."""
    sa = main_statement(a, name=name)
    sb = main_statement(b, name=name)
    return sa is not None and sa == sb


_AXIOMS_RE = re.compile(r"depends on axioms:\s*\[([^\]]*)\]")
_NO_AXIOMS_RE = re.compile(r"does not depend on any axioms")
_SORRY_RE = re.compile(r"declaration uses 'sorry'")


def parse_axioms(output: str) -> "list[str] | None":
    """The axiom list `#print axioms <name>` reported, or None when the
    output carries no such line (the declaration was never reached, so
    there is no verdict to read off it — not an empty one)."""
    text = output or ""
    last = None
    for last in _AXIOMS_RE.finditer(text):
        pass
    if last is not None:
        inner = last.group(1).strip()
        return [a.strip() for a in inner.split(",") if a.strip()]
    if _NO_AXIOMS_RE.search(text):
        return []
    return None


def has_sorry_warning(output: str) -> bool:
    """Whether Lean warned that a declaration in the file uses `sorry`."""
    return _SORRY_RE.search(output or "") is not None


def verdict(lake_rc: int, output: str, axioms: "list[str] | None", *,
            timed_out: bool = False) -> str:
    """`proved` / `failed` / `timeout` for one cold compile."""
    if timed_out:
        return "timeout"
    if lake_rc != 0:
        return "failed"
    if has_sorry_warning(output):
        return "failed"
    if axioms is None:
        return "failed"
    if not set(axioms) <= PROOF_AXIOMS:
        return "failed"
    return "proved"


#: Top-level declaration heads, LEFT-ANCHORED: an indented `theorem`
#: inside a proof (a `have`'s cousin) is not a declaration of the file.
_DECL_HEAD_RE = re.compile(
    r"^(?:@\[[^\]]*\][ \t]*)*"
    r"(?:(?:noncomputable|private|protected|partial|unsafe)[ \t]+)*"
    r"(?:theorem|lemma|def|abbrev|instance)[ \t]+",
    re.MULTILINE)


def decl_count(text: str) -> int:
    """How many top-level declarations the assembled file carries — the
    `lsp` arm's freedom to write many, counted."""
    return len(_DECL_HEAD_RE.findall(text or ""))


# ─── log readers (pure) ──────────────────────────────────────────────

def _read_jsonl(path: "Path | None") -> "list[dict]":
    """Every JSON object in a JSONL file; missing file / bad line → skip.
    A forensic reader must never be the thing that fails a run."""
    out: "list[dict]" = []
    if path is None or not Path(path).is_file():
        return out
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def gateway_tool_counts(path: "Path | None") -> dict:
    """What the gateway itself recorded for one spawn — the fields
    `lsp.gateway.state._log_for` writes: `tool_call` events by name,
    `validate_file`'s own verdict (`has_error` / `timed_out`), the
    elaboration wall, and the refused edits."""
    tools: "dict[str, int]" = {}
    validate_ok = validate_fail = elab_wall = refused = 0
    last_validate_ok: "bool | None" = None
    for ev in _read_jsonl(path):
        if ev.get("event") == "tool_call" and ev.get("name"):
            name = str(ev["name"])
            tools[name] = tools.get(name, 0) + 1
            if ev.get("timed_out") is True or ev.get("converged") is False:
                elab_wall += 1
            if name == "validate_file":
                ok = not ev.get("has_error") and not ev.get("timed_out")
                last_validate_ok = bool(ok)
                if ok:
                    validate_ok += 1
                else:
                    validate_fail += 1
        elif ev.get("outcome") == "refused":
            refused += 1
    return {"tools": tools, "validate_ok": validate_ok,
            "validate_fail": validate_fail, "elab_wall": elab_wall,
            "refused": refused, "last_validate_ok": last_validate_ok}


def _tool_use_blocks(obj) -> "list[dict]":
    """Every `type: tool_use` block anywhere under `obj`. Walked rather
    than addressed: the claude transcript's envelope shape is the CLI's
    to change, and a path spelled here would go quietly empty when it
    does."""
    found: "list[dict]" = []
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use":
            found.append(obj)
        for v in obj.values():
            found += _tool_use_blocks(v)
    elif isinstance(obj, list):
        for v in obj:
            found += _tool_use_blocks(v)
    return found


def transcript_tool_counts(path: "Path | None") -> dict:
    """The AGENT's side of the same story: which tools it actually
    called (native `Edit`/`Write` included — the arms name the MCP tools
    and forbid nothing, so which surface the agent reached for is a
    result, not a setting), and how many Bash calls were `lake`."""
    tools: "dict[str, int]" = {}
    bash_lake = 0
    for obj in _read_jsonl(path):
        for block in _tool_use_blocks(obj):
            name = str(block.get("name") or "")
            if not name:
                continue
            tools[name] = tools.get(name, 0) + 1
            if name == "Bash":
                args = block.get("input")
                cmd = ""
                if isinstance(args, dict):
                    cmd = str(args.get("command") or "").strip()
                if cmd.startswith("lake"):
                    bash_lake += 1
    return {"tools": tools, "bash_lake": bash_lake}


# ─── prompts ─────────────────────────────────────────────────────────

_AUX_SAME_FILE = (
    "You may add any number of auxiliary lemmas and definitions in the "
    "same file above `main`.")
_AUX_PROD = (
    "Auxiliary lemmas follow the production rule stated below.")

_HEADER = """\
You are proving one theorem in Lean 4 with Mathlib. The file `{patch}` currently holds
the statement `main` with `sorry`. Replace the `sorry` with a complete proof. {aux} Keep
the `theorem main` statement byte-identical, keep the `namespace` / `end` lines, do not edit
`Defs.lean` or `Root.lean`, and do not use `sorry`, `admit`, `native_decide`, or new axioms. The
framework injects `import Mathlib` and the Defs import at commit; imports already in the file are kept.
When the file elaborates with zero errors and no sorry warning, stop and reply with the single line
DONE. If you cannot finish, stop and reply with the single line GIVE_UP followed by one paragraph on
what blocked you.

{arm_block}

The Lean namespace is `{namespace}`; the paper below calls the same
definitions `{paper_name}`. The definitions are identical. `Defs.lean` (verbatim):

```lean
{defs}
```

Paper proof (verbatim):

{paper}
"""

_ARM_LSP = (
    "Your only way to check Lean is the MCP tools `apply_edit` (edit "
    "patch.lean), `errors_at`, `goal_at`, and `validate_file` "
    "(elaborates the whole file). There is no shell. Use `validate_file` "
    "to confirm the final state.")

_ARM_PROD_EXTRA = (
    "Production rule: one declaration per file. Every auxiliary lemma "
    "goes in its own file `{attempts}/new_<slug>.lean` (snake_case "
    "slug), declared first as `theorem <slug> ... := by sorry` inside "
    "the same namespace, validated with "
    "`validate_file(file=\"new_<slug>.lean\")`, then proved. "
    "`patch.lean` may cite those lemmas by name; `validate_file()` "
    "inlines them. Each file must start with a leading `--` comment "
    "block describing the declaration.")

_ARM_SHELL = (
    "Your only way to check Lean is the shell command "
    "`lake env lean {patch}` (absolute path; run it as given). Read the "
    "compiler output and fix the file with your file editing tools. "
    "There is no MCP Lean tool.")


def build_prompt(arm: str, *, attempts: Path, problem: str,
                 defs_text: str, paper_text: str) -> str:
    """The arm's prompt: one common header, one arm-specific block."""
    patch = (attempts / "patch.lean").as_posix()
    att = attempts.as_posix()
    if arm == "lsp":
        arm_block = _ARM_LSP
    elif arm == "prod":
        arm_block = _ARM_LSP + "\n\n" + _ARM_PROD_EXTRA.format(attempts=att)
    elif arm == "shell":
        arm_block = _ARM_SHELL.format(patch=patch)
    else:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")
    return _HEADER.format(
        patch=patch,
        aux=(_AUX_PROD if arm == "prod" else _AUX_SAME_FILE),
        arm_block=arm_block,
        namespace=f"Problems.{problem}",
        paper_name=PAPER_PROBLEM_NAME,
        defs=defs_text.rstrip("\n"),
        paper=paper_text.rstrip("\n"),
    )


# ─── the run ─────────────────────────────────────────────────────────

def lake_check(workspace: Path, path: Path,
               timeout: int = LAKE_TIMEOUT_SEC) -> "tuple[int, str, bool]":
    """`lake env lean <path>` in the workspace — `(rc, output, timed_out)`.
    The same call shape `lab.gauntlet.lake_ok` takes, with the whole
    output kept (the `#print axioms` line lives in it)."""
    try:
        r = subprocess.run(["lake", "env", "lean", str(path)],
                           cwd=str(workspace), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or ""), False
    except subprocess.TimeoutExpired:
        return 124, f"lake env lean exceeded {timeout}s", True
    except OSError as exc:
        return 127, f"lake not launchable: {type(exc).__name__}: {exc}", False


def usage_for(workspace: Path, pipeline_id: str) -> dict:
    """The `spawn_usage` rows `spawn_llm` wrote for this pipeline."""
    from ..state import db
    keys = ("input_tokens", "output_tokens", "cache_read_tokens",
            "cache_new_tokens", "turns")
    totals = {k: 0 for k in keys}
    totals["rows"] = 0
    db_path = workspace / "asterism.db"
    if not db_path.exists():
        return totals
    try:
        conn = db.connect_readonly(db_path)
    except Exception:  # noqa: BLE001 — a missing number is not a failed run
        return totals
    try:
        rows = conn.execute(
            "SELECT input_tokens, output_tokens, cache_read_tokens,"
            " cache_new_tokens, turns FROM spawn_usage"
            " WHERE pipeline_id = ?", (pipeline_id,)).fetchall()
    except Exception:  # noqa: BLE001
        rows = []
    finally:
        conn.close()
    for row in rows:
        totals["rows"] += 1
        for k in keys:
            totals[k] += int(row[k] or 0)
    return totals


def find_transcript(problem_dir: Path, session_id: str) -> "Path | None":
    """The claude session jsonl for this spawn. The CLI files it under
    the munge of the spawn's OWN cwd, which is the problem dir."""
    from .run import claude_transcript_dir
    d = claude_transcript_dir(problem_dir)
    if not d.is_dir():
        return None
    for f in sorted(d.glob("*.jsonl")):
        if session_id in f.name:
            return f
    return None


def _copy(src: "Path | None", dest_dir: Path) -> None:
    """Best-effort copy into the record directory."""
    if src is None:
        return
    try:
        if Path(src).is_file():
            shutil.copy2(src, dest_dir / Path(src).name)
    except OSError:
        pass


def _seat_env(model: str) -> None:
    """Point the formalizer seat at this experiment's model FOR THIS
    PROCESS. `config.get` reads the env before the yaml, so the live
    `Asterism.yaml` is neither read for this nor edited."""
    os.environ["ASTERISM_FORMALIZER_PROVIDER"] = "claude"
    if model:
        os.environ["ASTERISM_FORMALIZER_MODEL"] = model


def _ensure_gateway(workspace: Path):
    """A live gateway, and the Popen IF THIS RUN started it (so a
    gateway that was already serving is left alone at the end)."""
    from ..lsp import lifecycle
    if lifecycle.gateway_live_pid(workspace) is not None:
        return None
    # ASCII only: this console is cp950 and a stray em-dash would kill
    # the run at its first status line.
    print("[direct] no gateway up; starting one", flush=True)
    return lifecycle.start_gateway(workspace)


def run_rep(*, arm: str, rep: int, workspace: Path, problem: str,
            root_text: str, defs_text: str, paper_text: str,
            model: str, timeout_sec: int, out_dir: Path,
            dry_run: bool) -> dict:
    """One repetition, start to record. Sequential by construction —
    two of these at once would share the gateway's slot pool and the
    machine's RAM, and the number being measured is a cost."""
    from .. import pipeline
    from ..agent import runtime as rt
    from ..state import assemble, db

    pid = f"direct_{arm}_r{rep}_{uuid.uuid4().hex[:8]}"
    attempts = rt.attempts_dir_for(workspace, pid)
    (attempts / "patch.lean").write_text(root_text, encoding="utf-8")
    prompt = build_prompt(arm, attempts=attempts, problem=problem,
                          defs_text=defs_text, paper_text=paper_text)
    prompt_path = attempts / "direct_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    problem_dir = db.problem_dir(workspace, problem)
    shell_allow = SHELL_ALLOW if arm == "shell" else ()

    if dry_run:
        _dry_run_report(arm, pid, attempts, prompt_path, prompt,
                        problem_dir, shell_allow, model, timeout_sec)
        return {"arm": arm, "rep": rep, "pid": pid, "dry_run": True}

    if arm in ("lsp", "prod"):
        mcp_config_path = pipeline._write_mcp_config(
            attempts, workspace, attempts / "patch.lean",
            pipeline_id=pid, problem=problem,
            kind=("direct" if arm == "lsp" else "Backward"))
    else:
        mcp_config_path = pipeline.write_tools_mcp_config(
            attempts, workspace, "formalizer", problem=problem)

    session_id = str(uuid.uuid4())
    t0 = time.monotonic()
    try:
        rc = rt.spawn_llm(
            kind="formalizer", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts,
            session_id=session_id, timeout_sec=timeout_sec,
            mcp_config_path=mcp_config_path, usage_workspace=workspace,
            usage_problem=problem, usage_pipeline_id=pid,
            shell_allow=shell_allow)
    finally:
        # The session, not the directory: the attempts tree IS the
        # evidence and nothing here deletes it.
        pipeline._release_session(attempts)
    wall_sec = round(time.monotonic() - t0, 1)
    print(f"[direct] {pid}: rc={rc} wall={wall_sec}s", flush=True)

    rec_dir = out_dir / pid
    rec_dir.mkdir(parents=True, exist_ok=True)
    patch_text = ""
    try:
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
    except OSError:
        pass

    inlined: "list[str]" = []
    if arm == "prod":
        from ..lsp.gateway import leantext
        final, _lm, inlined = leantext._build_compilation_unit(
            patch_text, problem, workspace, attempts)
    else:
        final = assemble.ensure_framework_imports(
            patch_text, problem=problem, workspace=workspace)
    (rec_dir / "final.lean").write_text(final, encoding="utf-8")
    check_path = rec_dir / "final_check.lean"
    check_path.write_text(
        final + f"\n#print axioms Problems.{problem}.main\n",
        encoding="utf-8")

    lake_rc, lake_out, lake_timeout = lake_check(workspace, check_path)
    (rec_dir / "final_check.out.txt").write_text(lake_out, encoding="utf-8")
    axioms = parse_axioms(lake_out)
    v = verdict(lake_rc, lake_out, axioms, timed_out=lake_timeout)
    if v == "failed" and rc == 124:
        # The spawn never finished; the file it left behind is a
        # snapshot of unfinished work, not a refutation.
        v = "timeout"

    gw_log = workspace / ".asterism" / "mcp_logs" / f"{pid}.jsonl"
    gw = gateway_tool_counts(gw_log if arm != "shell" else None)
    transcript = find_transcript(problem_dir, session_id)
    record = {
        "arm": arm,
        "rep": rep,
        "pid": pid,
        "model": model,
        "rc": rc,
        "wall_sec": wall_sec,
        "verdict": v,
        "statement_identical": statements_identical(root_text, final),
        "axioms": axioms,
        "sorry_warning": has_sorry_warning(lake_out),
        "lake_rc": lake_rc,
        "final_lines": final.count("\n") + 1 if final else 0,
        "final_decl_count": decl_count(final),
        "inlined_siblings": inlined,
        "usage": usage_for(workspace, pid),
        "gateway_tools": gw,
        "transcript_tools": transcript_tool_counts(transcript),
        "last_validate_ok": gw["last_validate_ok"],
        "false_green": gw["last_validate_ok"] is True and v != "proved",
    }
    (rec_dir / "run_record.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    _copy(attempts / "patch.lean", rec_dir)
    for stub in sorted(attempts.glob("new_*.lean")):
        _copy(stub, rec_dir)
    _copy(attempts / "_parser_state.json", rec_dir)
    _copy(attempts / "_spawn.stderr", rec_dir)
    _copy(prompt_path, rec_dir)
    _copy(gw_log if gw_log.is_file() else None, rec_dir)
    _copy(transcript, rec_dir)
    print(f"[direct] {pid}: {v} "
          f"(statement_identical={record['statement_identical']}, "
          f"false_green={record['false_green']})", flush=True)
    return record


def _dry_run_report(arm: str, pid: str, attempts: Path, prompt_path: Path,
                    prompt: str, problem_dir: Path,
                    shell_allow: "tuple[str, ...]", model: str,
                    timeout_sec: int) -> None:
    """Everything but the spawn. The allowlist is printed because it is
    the arm's actual boundary — the sentence in the prompt is only what
    the agent is TOLD."""
    from ..llm import claude_cli
    from ..llm.base import LLMRequest
    print(f"[dry-run] arm={arm} pid={pid} model={model or '(seat default)'} "
          f"timeout={timeout_sec}s", flush=True)
    print(f"[dry-run] seed: {(attempts / 'patch.lean').as_posix()}", flush=True)
    print(f"[dry-run] prompt: {prompt_path.as_posix()} "
          f"({len(prompt)} chars)", flush=True)
    req = LLMRequest(kind="formalizer", prompt_path=prompt_path,
                     problem_dir=problem_dir, attempts_dir=attempts,
                     timeout_sec=timeout_sec, shell_allow=shell_allow,
                     # Both wirings carry an MCP config — the gateway's
                     # plus `asterism_tools` for lsp/prod, the tools
                     # server alone for shell — and the allowlist below
                     # differs by which.
                     mcp_config_path=(attempts / "_mcp_tools.json"
                                      if arm == "shell"
                                      else attempts / "_mcp_config.json"))
    print(f"[dry-run] --allowed-tools {claude_cli._compose_allowed_tools(req)}",
          flush=True)
    print(f"[dry-run] --disallowedTools carries Bash: {not shell_allow}",
          flush=True)
    print("[dry-run] no gateway session registered, no spawn", flush=True)


# ─── summaries ───────────────────────────────────────────────────────

_SUMMARY_HEAD = (
    "| arm | rep | verdict | stmt_same | wall_s | out_tok | turns | "
    "gateway_tools | agent_tools | false_green |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")


def _summary_row(rec: dict) -> str:
    gw = rec.get("gateway_tools") or {}
    tt = rec.get("transcript_tools") or {}
    usage = rec.get("usage") or {}
    return (f"| {rec.get('arm')} | {rec.get('rep')} | {rec.get('verdict')} "
            f"| {rec.get('statement_identical')} | {rec.get('wall_sec')} "
            f"| {usage.get('output_tokens')} | {usage.get('turns')} "
            f"| {_fmt_counts(gw.get('tools'))} "
            f"| {_fmt_counts(tt.get('tools'))} "
            f"| {rec.get('false_green')} |\n")


def _fmt_counts(counts: "dict | None") -> str:
    if not counts:
        return "-"
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def write_summaries(out_dir: Path, arm: str, records: "list[dict]") -> None:
    """One table per arm, and one growing table across all of them."""
    rows = "".join(_summary_row(r) for r in records if not r.get("dry_run"))
    per_arm = out_dir / f"summary_{arm}.md"
    per_arm.write_text(f"# direct-session: arm `{arm}`\n\n"
                       + _SUMMARY_HEAD + rows, encoding="utf-8")
    all_path = out_dir / "summary_all.md"
    if not all_path.exists():
        all_path.write_text("# direct-session: all arms\n\n" + _SUMMARY_HEAD,
                            encoding="utf-8")
    with all_path.open("a", encoding="utf-8") as f:
        f.write(rows)


# ─── CLI ─────────────────────────────────────────────────────────────

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m Tooling.lab.direct_session",
        description="One agent, one theorem, three Lean surfaces.")
    p.add_argument("--problem", required=True,
                   help="dotted problem slug, e.g. "
                        "Combinatorics.single_root_direct")
    p.add_argument("--paper", required=True,
                   help="the paper proof handed to the agent verbatim")
    p.add_argument("--arm", required=True, choices=list(ARMS))
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--model", default="",
                   help="formalizer model for THIS process only")
    p.add_argument("--timeout-sec", type=int, default=3600)
    p.add_argument("--out", required=True, help="where the records go")
    p.add_argument("--workspace", default="",
                   help="the LIVE workspace (default: cwd)")
    p.add_argument("--dry-run", action="store_true",
                   help="write the seed and the prompt, spawn nothing")
    return p


def main(argv: "list[str] | None" = None) -> int:
    args = _parser().parse_args(argv)
    workspace = Path(args.workspace).resolve() if args.workspace \
        else Path.cwd().resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    problem_dir = workspace / "Problems" / Path(*args.problem.split("."))
    root = problem_dir / "Root.lean"
    defs = problem_dir / "Defs.lean"
    paper = Path(args.paper)
    if not paper.is_absolute():
        paper = workspace / paper
    for p in (root, defs, paper):
        if not p.is_file():
            print(f"[direct] missing input: {p}", file=sys.stderr)
            return 2
    root_text = root.read_text(encoding="utf-8")
    defs_text = defs.read_text(encoding="utf-8")
    paper_text = paper.read_text(encoding="utf-8")
    _seat_env(args.model)

    started_gateway = None
    if args.arm in ("lsp", "prod") and not args.dry_run:
        started_gateway = _ensure_gateway(workspace)
    records: "list[dict]" = []
    try:
        for rep in range(1, args.reps + 1):
            records.append(run_rep(
                arm=args.arm, rep=rep, workspace=workspace,
                problem=args.problem, root_text=root_text,
                defs_text=defs_text, paper_text=paper_text,
                model=args.model, timeout_sec=args.timeout_sec,
                out_dir=out_dir, dry_run=args.dry_run))
    finally:
        if started_gateway is not None:
            # Only a gateway THIS run started is stopped: one that was
            # already serving belongs to whoever started it.
            try:
                started_gateway.terminate()
                started_gateway.wait(timeout=30)
            except Exception:  # noqa: BLE001 — teardown, best-effort
                pass
    if not args.dry_run:
        write_summaries(out_dir, args.arm, records)
    proved = sum(1 for r in records if r.get("verdict") == "proved")
    print(f"[direct] arm={args.arm} reps={len(records)} proved={proved}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
