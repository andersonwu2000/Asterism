"""`asterism lab run standard <set|item|all>` — the standard test sets.

An experiment asks a question nobody has asked yet; a STANDARD SET asks
one that has been asked before and has a recorded answer. Same four
nouns (slice x workspace x driver -> record), one thing added: every
item carries an `expected.json`, so the record is SCORED and the score
is appended to `<root>/scorecard.md` — the only file under the lab root
this runner writes outside `runs/`.

    <root>/sets/standard.yaml         the table (the owner's; read here)
    <root>/sets/base/Problems/...     seed problems, initialised into
                                      the base workspace by `lab build`
    <root>/sets/<set>/<item>/...      that item's inputs + expectation
    <root>/scorecard.md               one row per item, ever appended

THREE THINGS THIS FILE IS RESPONSIBLE FOR.

  READING THE TABLE. Every key is checked and an unknown one refuses,
  for the reason a lab.yaml's are: the failure a hand-edited table is
  exposed to is not a crash but an item that runs against the setting
  it meant to change and reports green. A set's `kind:` / `problem:` /
  `group:` / `trigger:` / `seats:` are DEFAULTS its items inherit, so
  five traps are judged against one charter rather than five copies of
  one line.

  ONE FRESH WORKSPACE PER ITEM, not per set. The judge leaves no scene
  behind — it writes a projection and `spawn_usage` rows, no goals, no
  revisions — so a shared workspace would be sound on the DB. It is not
  sound on the RECORD: `claude` files its transcript under a name
  derived from the CWD (`run.claude_transcript_dir`), so items sharing
  a workspace share one transcript directory, and `tools_touched` —
  read out of exactly that — could no longer be attributed to the item
  that earned it. A record that cannot say which item it describes is
  the failure the whole lab exists to prevent, and one `copytree` of
  the base per item is what it costs.

  SCORING FROM THE RECORD AND NOTHING ELSE. The workspace is gone by
  the time anyone reads the score, so it is computed before the record
  is written (`run.run_once(score=...)`) and lands inside it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import LabError, base_dir, runs_dir, snapshots_dir
from . import build as _build
from . import run as _run
from . import snapshot as _snapshot
from . import spec as _spec

#: `<root>/sets/` and the table in it.
SETS_DIRNAME = "sets"
STANDARD_BASENAME = "standard.yaml"

#: The run directory every standard item is filed under
#: (`<root>/runs/standard/<set>_<item>_r<n>/`), and therefore a name a
#: hand-written experiment may not take.
EXPERIMENT_NAME = "standard"

#: The scorecard. Appended to, never rewritten: the cross-model
#: baselines a set is read against are the rows already in it.
SCORECARD_BASENAME = "scorecard.md"

_TOP_KEYS = ("base", "sets", "notes")
_BASE_KEYS = ("problems", "reuse_workspace_problems", "notes")
#: What a set hands down to its items.
_INHERITED = ("problem", "group", "trigger", "seats", "prompts")
_SET_KEYS = ("kind", "items", "expected", "notes") + _INHERITED
_ITEM_KEYS = ("kind", "expected", "notes") + _INHERITED

#: What each kind's `expected.json` may say. Refused at LOAD time, not
#: at scoring time: a misspelled expectation would otherwise be a check
#: that silently never ran, on a scorecard that says the item passed.
EXPECTED_KEYS: "dict[str, tuple[str, ...]]" = {
    "judge_round": ("verdict", "parsed", "must_fire", "must_not_fire"),
    "daemon": ("outcome", "proved_at_least", "revisions_at_least",
               "wall_sec_at_most", "tools_touched"),
    "theory_wake": ("outcome", "document", "rounds_at_most"),
    "strategist_wake": ("outcome",),
    "push_wake": ("outcome",),
    "gauntlet": ("bricks_at_least",),
}
#: Free prose, on every kind — the owner's note to the next reader.
_EXPECTED_PROSE = ("note",)

#: The prompt whose sha256 the scorecard carries, per kind: the one
#: whose wording the item is actually measuring. Read out of the
#: record's `prompt_sha256` (what the workspace HELD), never out of the
#: arm's declaration.
SCORECARD_PROMPT = {
    "judge_round": "adversary/adversary.md",
    "theory_wake": "theorist/theory.md",
    "strategist_wake": "strategist/routine.md",
    "push_wake": "strategist/routine.md",
    "daemon": "strategist/routine.md",
}


# ---------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    """One standard item: a driver, its inputs, and its expectation."""
    set_name: str
    key: str
    kind: str
    problem: str
    options: dict
    expected: dict
    expected_path: Path
    seats: "dict[str, dict]" = field(default_factory=dict)
    prompts: "dict[str, Path]" = field(default_factory=dict)
    #: The problem lives in the LIVE workspace, so the scene has to be
    #: taken as a slice; a seeded one is already in the base.
    needs_slice: bool = False

    @property
    def name(self) -> str:
        """`<set>/<item>`, or just `<set>` for a set that IS one item —
        `gauntlet/gauntlet` names one thing twice."""
        return (self.set_name if self.key == self.set_name
                else f"{self.set_name}/{self.key}")

    @property
    def arm(self) -> str:
        """The run directory's arm component — `/` is not one."""
        return self.name.replace("/", "_")


@dataclass(frozen=True)
class StandardSets:
    path: Path
    base_problems: "tuple[Path, ...]"
    reuse_problems: "tuple[str, ...]"
    items: "tuple[Item, ...]"

    @property
    def dir(self) -> Path:
        return self.path.parent

    @property
    def set_names(self) -> "list[str]":
        out: "list[str]" = []
        for i in self.items:
            if i.set_name not in out:
                out.append(i.set_name)
        return out


def standard_path(root: Path) -> Path:
    return Path(root) / SETS_DIRNAME / STANDARD_BASENAME


def _read(root: Path) -> "tuple[dict, Path]":
    import yaml
    path = standard_path(root)
    if not path.is_file():
        raise LabError(
            f"no standard sets at {path} — `lab run standard` reads the "
            f"owner's table of sets; it never invents one. The lab root "
            f"is the directory that HOLDS `sets/`.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LabError(f"{path} is not valid YAML: {exc}") from None
    if not isinstance(raw, dict):
        raise LabError(f"{path} must be a mapping at the top level")
    _spec._refuse_unknown(str(path), raw, _TOP_KEYS)
    return raw, path


def base_problem_dirs(root: Path) -> "list[Path]":
    """`base.problems`, absolute — or [] when the root holds no table.

    Read WITHOUT parsing the sets: `lab build` calls this on every base
    materialisation, including for experiments that have nothing to do
    with the standard sets, and a broken `sets:` block must not stop
    them from building.
    """
    if not standard_path(root).is_file():
        return []
    raw, path = _read(root)
    base = dict(raw.get("base") or {})
    _spec._refuse_unknown(f"{path} base", base, _BASE_KEYS)
    out: "list[Path]" = []
    for rel in list(base.get("problems") or []):
        p = (path.parent / str(rel)).resolve()
        if not (p / "problem.json").is_file():
            raise LabError(
                f"{path}: `base.problems` names {rel} — no problem.json at "
                f"{p}. A seed problem is a directory with problem.json "
                f"(and optionally Root.lean / Defs.lean), the same shape "
                f"`asterism init` takes.")
        out.append(p)
    return out


def _seed_slug(sets_dir: Path, pdir: Path) -> str:
    """`sets/base/Problems/Lab/tiny` -> `Lab.tiny` — the slug the base
    will register it under (`db.slug_from_problem_dir`'s rule)."""
    rel = Path(pdir).resolve().relative_to(
        (sets_dir / "base" / "Problems").resolve())
    return ".".join(rel.parts)


def load(root: Path) -> StandardSets:
    """Read and validate `<root>/sets/standard.yaml`."""
    raw, path = _read(root)
    sets_dir = path.parent
    base_problems = base_problem_dirs(root)
    reuse = tuple(str(p) for p in
                  (dict(raw.get("base") or {}).get(
                      "reuse_workspace_problems") or []))
    seeded = {_seed_slug(sets_dir, p) for p in base_problems}

    sets_raw = raw.get("sets") or {}
    if not isinstance(sets_raw, dict) or not sets_raw:
        raise LabError(f"{path}: `sets:` must name at least one set")
    items: "list[Item]" = []
    for set_name, block in sets_raw.items():
        items += _parse_set(str(set_name), block, path=path,
                            seeded=seeded, reuse=reuse)
    return StandardSets(path=path,
                        base_problems=tuple(base_problems),
                        reuse_problems=reuse, items=tuple(items))


def _parse_set(set_name: str, block, *, path: Path, seeded: "set[str]",
               reuse: "tuple[str, ...]") -> "list[Item]":
    if not isinstance(block, dict):
        raise LabError(f"{path}: set {set_name!r} is not a mapping")
    kind = str(block.get("kind") or "").strip()
    allowed = _SET_KEYS + _kind_keys(f"set {set_name!r}", kind, path)
    _spec._refuse_unknown(f"{path} set {set_name!r}", block, allowed)
    defaults = {k: block[k] for k in allowed
                if k in block and k not in ("items", "notes")}
    raw_items = block.get("items")
    if raw_items is None:
        # A set with no `items:` IS one item — the gauntlet's shape.
        return [_parse_item(set_name, set_name, {}, defaults,
                            path=path, seeded=seeded, reuse=reuse)]
    if not isinstance(raw_items, dict) or not raw_items:
        raise LabError(
            f"{path}: set {set_name!r} `items:` must be a mapping of "
            f"<name>: <item>, or be absent (then the set is one item)")
    return [_parse_item(set_name, str(k), v, defaults, path=path,
                        seeded=seeded, reuse=reuse)
            for k, v in raw_items.items()]


def _kind_keys(where: str, kind: str, path: Path) -> "tuple[str, ...]":
    if not kind:
        return ()
    if kind not in _spec.DRIVER_KINDS:
        raise LabError(
            f"{path}: {where}: kind {kind!r} is not a driver — have "
            f"{sorted(_spec.DRIVER_KINDS)}")
    return _spec.DRIVER_KINDS[kind]


def _parse_item(set_name: str, key: str, raw, defaults: dict, *,
                path: Path, seeded: "set[str]",
                reuse: "tuple[str, ...]") -> Item:
    where = f"item {set_name}/{key}"
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise LabError(f"{path}: {where} is not a mapping")
    merged = {**defaults, **raw}
    kind = str(merged.get("kind") or "").strip()
    if not kind:
        raise LabError(
            f"{path}: {where} names no `kind:` and its set declares none "
            f"— have {sorted(_spec.DRIVER_KINDS)}")
    kind_keys = _kind_keys(where, kind, path)
    _spec._refuse_unknown(f"{path} {where}", raw, _ITEM_KEYS + kind_keys)

    options = {k: merged[k] for k in kind_keys if k in merged}
    _spec._check_options(f"{set_name}/{key}", kind, options, path.parent)
    # Before the scene: an item with no expectation is not a standard
    # item at all, so it is refused before anything asks where it runs.
    expected, expected_path = _load_expected(where, merged, kind, path)

    problem = str(options.get("scope") or merged.get("problem") or "").strip()
    if not problem and kind == "gauntlet":
        # The gauntlet's bricks are self-contained files and it touches
        # no DB — a problem is needed only as the spawn's READ SCOPE
        # (`problem_dir`), so the base's own seed problem serves, and
        # requiring the table to name one would be asking the operator
        # for a fact that does not affect the measurement.
        if not seeded:
            raise LabError(
                f"{path}: {where}: a gauntlet needs some problem "
                f"directory as its spawn's read scope, and the base "
                f"seeds none — add one to `base.problems`, or name a "
                f"`problem:` on the set")
        problem = sorted(seeded)[0]
    if not problem:
        raise LabError(
            f"{path}: {where} names no problem — a `daemon` item's is its "
            f"`scope:`, every other kind's is `problem:` on the item or "
            f"its set")
    needs_slice = problem in reuse
    if not needs_slice and problem not in seeded:
        raise LabError(
            f"{path}: {where} runs on {problem!r}, which is neither seeded "
            f"into the base (`base.problems`: {sorted(seeded)}) nor listed "
            f"in `base.reuse_workspace_problems` ({list(reuse)}). A "
            f"standard item must say where its scene comes from — a "
            f"problem that is in neither list is one no workspace has.")

    seats = {str(k): _spec._seat_spec(str(k), v)
             for k, v in dict(merged.get("seats") or {}).items()}
    prompts: "dict[str, Path]" = {}
    for rel, src in dict(merged.get("prompts") or {}).items():
        p = (path.parent / str(src)).resolve()
        if not p.is_file():
            raise LabError(
                f"{path}: {where}: prompt overlay {src!r} is not a file at "
                f"{p} — overlay paths are relative to standard.yaml")
        prompts[str(rel).replace("\\", "/").lstrip("/")] = p
    return Item(set_name=set_name, key=key, kind=kind, problem=problem,
                options=options, expected=expected,
                expected_path=expected_path, seats=seats, prompts=prompts,
                needs_slice=needs_slice)


def _load_expected(where: str, merged: dict, kind: str,
                   path: Path) -> "tuple[dict, Path]":
    rel = merged.get("expected")
    if not rel:
        raise LabError(
            f"{path}: {where} names no `expected:` — an item scored "
            f"against nothing is not a standard item, it is a run that "
            f"happened. Point it at the set's expected.json.")
    p = (path.parent / str(rel)).resolve()
    if not p.is_file():
        raise LabError(f"{path}: {where}: no expectation file at {p}")
    try:
        exp = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise LabError(f"{p} is not valid JSON: {exc}") from None
    if not isinstance(exp, dict):
        raise LabError(f"{p} must be a JSON object")
    _spec._refuse_unknown(
        f"{p} ({kind})", exp, EXPECTED_KEYS.get(kind, ()) + _EXPECTED_PROSE)
    if not set(exp) - set(_EXPECTED_PROSE):
        raise LabError(
            f"{p} states no expectation — it may say "
            f"{sorted(EXPECTED_KEYS.get(kind, ()))} for a {kind} item")
    return exp, p


# ---------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------

def _check(ok: bool, **fields) -> dict:
    return {"ok": bool(ok), **fields}


def _fired(criteria: dict, key: str) -> bool:
    """Whether criterion `key` carries a fired bullet, read the way the
    framework reads it (`adversary.split_criterion`) — a private copy of
    that parse is the drift that made every rebut read as `passed` for a
    week (44ff4321)."""
    from ..pipeline import adversary
    state, _ = adversary.split_criterion(criteria.get(key))
    return state == "fired"


def _score_judge(expected: dict, result: dict) -> dict:
    rounds = list(result.get("rounds") or [])
    verdict = (rounds[-1] or {}).get("verdict") if rounds else None
    criteria = dict((verdict or {}).get("criteria") or {})
    checks: dict = {}
    if "parsed" in expected:
        checks["parsed"] = _check(bool(verdict) == bool(expected["parsed"]),
                                  got=verdict is not None,
                                  want=bool(expected["parsed"]))
    if "verdict" in expected:
        got = (verdict or {}).get("verdict")
        checks["verdict"] = _check(got == expected["verdict"], got=got,
                                   want=expected["verdict"])
    want_fire = [str(k) for k in (expected.get("must_fire") or [])]
    if want_fire:
        fired = [k for k in want_fire if _fired(criteria, k)]
        checks["must_fire"] = _check(len(fired) == len(want_fire),
                                     want=want_fire, fired=fired,
                                     missing=[k for k in want_fire
                                              if k not in fired])
    want_clear = [str(k) for k in (expected.get("must_not_fire") or [])]
    if want_clear:
        fired = [k for k in want_clear if _fired(criteria, k)]
        checks["must_not_fire"] = _check(not fired, want=want_clear,
                                         fired=fired)
    return checks


def _score_daemon(expected: dict, record: dict, result: dict) -> dict:
    produced = dict(result.get("produced") or {})
    checks: dict = {}
    for key, col in (("proved_at_least", "proved"),
                     ("revisions_at_least", "revisions")):
        if key in expected:
            got = int(produced.get(col) or 0)
            checks[key] = _check(got >= int(expected[key]), got=got,
                                 want=int(expected[key]))
    if "wall_sec_at_most" in expected:
        got = float(record.get("wall_sec") or 0.0)
        checks["wall_sec_at_most"] = _check(got <= float(
            expected["wall_sec_at_most"]), got=got,
            want=float(expected["wall_sec_at_most"]))
    if expected.get("tools_touched"):
        want = [str(t) for t in expected["tools_touched"]]
        seen = tools_seen(Path(record["out_dir"])) if record.get("out_dir") \
            else set()
        missing = [t for t in want if t not in seen]
        checks["tools_touched"] = _check(not missing, want=want,
                                         missing=missing,
                                         seen=sorted(seen))
    return checks


def _score_theory(expected: dict, result: dict) -> dict:
    doc = dict(result.get("theory_document") or {})
    checks: dict = {}
    if "document" in expected:
        checks["document"] = _check(
            str(doc.get("status") or "") == str(expected["document"]),
            got=doc.get("status"), want=expected["document"])
    if "rounds_at_most" in expected:
        got = int(doc.get("rounds") or 0)
        checks["rounds_at_most"] = _check(got <= int(
            expected["rounds_at_most"]), got=got,
            want=int(expected["rounds_at_most"]))
    return checks


def _score_gauntlet(expected: dict, result: dict) -> dict:
    passed = sum(1 for b in (result.get("bricks") or []) if b.get("ok"))
    total = len(result.get("bricks") or [])
    if "bricks_at_least" not in expected:
        return {}
    return {"bricks_at_least": _check(passed >= int(
        expected["bricks_at_least"]), got=passed, of=total,
        want=int(expected["bricks_at_least"]))}


def score(kind: str, expected: dict, record: dict) -> dict:
    """`{ok, checks}` for one finished item — derived from the record
    and the expectation, and from nothing else."""
    result = dict(record.get("driver_result") or {})
    checks: dict = {}
    if "outcome" in expected:
        got = record.get("outcome")
        checks["outcome"] = _check(got == expected["outcome"], got=got,
                                   want=expected["outcome"])
    if kind == "judge_round":
        checks.update(_score_judge(expected, result))
    elif kind == "daemon":
        checks.update(_score_daemon(expected, record, result))
    elif kind == "theory_wake":
        checks.update(_score_theory(expected, result))
    elif kind == "gauntlet":
        checks.update(_score_gauntlet(expected, result))
    return {"ok": bool(checks) and all(c["ok"] for c in checks.values()),
            "checks": checks}


# ---------------------------------------------------------------------
# which tools a run's spawns actually reached
# ---------------------------------------------------------------------

#: `asterism_tools__compute`, `mcp__lsp__goal_at` — both providers spell
#: an MCP tool as `<server>__<tool>` somewhere in their own transcript
#: (claude as `mcp__<server>__<tool>` in a tool_use block, codex as the
#: bare pair in its rollout), so one pattern reads both.
_TOOL_RE = re.compile(r"(?:asterism_tools|lsp)__([A-Za-z_][A-Za-z0-9_]*)")


def tools_seen(out_dir: Path) -> "set[str]":
    """Every framework tool this run's spawns called, out of `_out/`.

    TWO SOURCES, unioned, because neither is complete on its own:
      * `_out/transcripts/` — both providers' own session records,
        copied out by `run.collect_transcripts`. This is where the
        `asterism_tools` half lives (compute / loogle / inspect /
        validate_json): that server is a stdio MCP the provider talks to
        directly, so the gateway never sees those calls.
      * `_out/mcp_logs/` — the gateway's own per-call log
        (`{"event": "tool_call", "name": …}`), copied out by
        `run.collect_mcp_logs`. Authoritative for the LSP half
        (apply_edit / validate_file / goal_at / errors_at) and present
        even for a seat that filed no transcript.

    Read line by line: a transcript is tens of megabytes and nothing
    here needs it in memory at once.
    """
    out_dir = Path(out_dir)
    seen: "set[str]" = set()
    tdir = out_dir / "transcripts"
    if tdir.is_dir():
        for p in sorted(tdir.rglob("*")):
            if not p.is_file():
                continue
            with p.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    seen.update(_TOOL_RE.findall(line))
    ldir = out_dir / "mcp_logs"
    if ldir.is_dir():
        for p in sorted(ldir.glob("*.jsonl")):
            with p.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ev, dict) and ev.get("event") == "tool_call":
                        if ev.get("name"):
                            seen.add(str(ev["name"]))
    return seen


# ---------------------------------------------------------------------
# the scorecard
# ---------------------------------------------------------------------

#: Deliberately WITHOUT a `feedback_records` column (2026-09-07). The
#: count is in every `run_record.json` and this table has no natural
#: place for it — every column here is either the item's identity or its
#: expectation-vs-result, and the agents' complaints are neither. Adding
#: one would also be silent corruption: the file is APPENDED to and its
#: header is written once, so a tenth cell on new rows would sit under a
#: nine-column header beside every baseline row this set is read
#: against. `run_record.feedback_records` is where the count lives.
_COLUMNS = ("date", "set/item", "kind", "seats", "prompt sha", "expected",
            "got", "ok", "run_record")

_HEADER = (
    "# Standard test scorecard\n\n"
    "_One row per item, appended by `asterism lab run standard …`. Never\n"
    "rewritten: the baselines a set is read against are the rows already\n"
    "here._\n\n"
    "| " + " | ".join(_COLUMNS) + " |\n"
    "|" + "|".join(["---"] * len(_COLUMNS)) + "|\n")


def scorecard_path(root: Path) -> Path:
    return Path(root) / SCORECARD_BASENAME


def _cell(value) -> str:
    text = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text.replace("|", "\\|").replace("\n", " ").strip() or "—"


def _seats_cell(record: dict) -> str:
    seats = {k: v for k, v in (record.get("seats") or {}).items()
             if isinstance(v, dict)}
    return " ".join(
        f"{k}={v.get('provider') or '?'}/{v.get('model') or '?'}"
        for k, v in sorted(seats.items())) or "—"


def prompt_sha(record: dict, kind: str) -> str:
    """The sha of the prompt this kind's item is measuring — out of the
    record's `prompt_sha256`, which is what the WORKSPACE held."""
    hashes = dict(record.get("prompt_sha256") or {})
    rel = SCORECARD_PROMPT.get(kind)
    if rel and hashes.get(rel):
        return f"{rel.split('/')[-1]} {hashes[rel][:12]}"
    own = (record.get("driver_result") or {}).get("prompt_sha256")
    return str(own)[:12] if own else "—"


def _got_cell(score_: dict) -> str:
    """What each check actually saw, labelled.

    A criterion list is unreadable unlabelled: `must_fire=["1"]` and
    `tools_touched=["compute"]` mean opposite things (one fired, one is
    missing), and a scorecard read a month later is the only account of
    the run there is."""
    bits = []
    for name, chk in (score_.get("checks") or {}).items():
        if not isinstance(chk, dict):
            continue
        if "got" in chk:
            val = _cell(chk["got"])
        elif chk.get("missing"):
            val = "missing " + _cell(chk["missing"])
        elif chk.get("fired"):
            val = "fired " + _cell(chk["fired"])
        else:
            val = "ok" if chk.get("ok") else "not met"
        bits.append(f"{name}={val}")
    return "; ".join(bits) or "—"


def append_scorecard(root: Path, *, name: str, kind: str, record: dict,
                     record_path: Path, expected: dict, score: dict) -> Path:
    """One row. Creates the file with its header if it is not there."""
    path = scorecard_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_HEADER, encoding="utf-8")
    try:
        rel = Path(record_path).resolve().relative_to(
            Path(root).resolve()).as_posix()
    except ValueError:
        rel = Path(record_path).as_posix()
    want = {k: v for k, v in expected.items() if k not in _EXPECTED_PROSE}
    row = [
        str(record.get("finished_utc")
            or datetime.now(timezone.utc).isoformat())[:19] + "Z",
        name, kind, _seats_cell(record), prompt_sha(record, kind),
        _cell(want), _got_cell(score), "yes" if score.get("ok") else "NO",
        rel,
    ]
    with path.open("a", encoding="utf-8") as fh:
        fh.write("| " + " | ".join(_cell(c) for c in row) + " |\n")
    return path


# ---------------------------------------------------------------------
# running
# ---------------------------------------------------------------------

def select(sets: StandardSets, target: str) -> "list[Item]":
    """The items `<set|item|all>` names, in table order."""
    want = str(target or "").strip()
    if want in ("all", "*"):
        return list(sets.items)
    hits = [i for i in sets.items
            if want in (i.name, i.set_name, i.key)]
    if not hits:
        raise LabError(
            f"no standard set or item {want!r} — {sets.path} has sets "
            f"{sets.set_names} and items "
            f"{[i.name for i in sets.items]} (or `all`)")
    return hits


def cached_slice(root: Path, *, workspace: Path, problem: str):
    """The slice for a problem the LIVE workspace holds — reused when
    one is already under `<root>/snapshots/`, taken once when not.

    `snapshot.ensure_slice` deliberately re-takes an un-rewound slice
    every time (it is named for the instant it was taken, and the live
    board never stops). A standard set wants the opposite: the same
    scene across a whole run and across the runs a scorecard compares,
    so an existing slice of that problem is REUSED and the operator
    retakes one by deleting it (or by `lab snapshot --scope`).
    """
    have = [s for s in _snapshot.list_slices(root)
            if s.problem == problem and not s.cutoff]
    if have:
        newest = max(have, key=lambda s: str(s.manifest.get("taken_utc") or ""))
        print(f"[lab] reusing slice {newest.id}", flush=True)
        return newest
    print(f"[lab] no slice of {problem} under {snapshots_dir(root)} — "
          f"taking one", flush=True)
    return _snapshot.take(Path(workspace), root, problem=problem)


def _experiment(sets: StandardSets, item: Item,
                seats: "dict[str, str] | None") -> _spec.Experiment:
    """A one-arm `Experiment` for this item, so the standard runner goes
    through the SAME build and record path an experiment does. A second
    builder would be a second definition of what a lab workspace is."""
    merged = dict(item.seats)
    for seat, raw in (seats or {}).items():
        merged[str(seat)] = _spec._seat_spec(str(seat), raw)
    arm = _spec.Arm(name=item.arm, kind=item.kind, prompts=dict(item.prompts),
                    seats=merged, options=dict(item.options))
    return _spec.Experiment(name=EXPERIMENT_NAME, path=sets.path,
                            snapshot=None, rewind=None, code_commit=None,
                            reps=1, arms={item.arm: arm})


def preflight(item: Item) -> None:
    """Whatever an item's inputs cost to CHECK, checked before any
    workspace is built — the lab's own rule: a driver that discovers
    its inputs are missing has already copied a base, imported a slice
    and warmed a seat, and the operator finds out minutes later.

    Only the gauntlet has an input the table cannot validate on its
    own: its bricks are a directory of Lean files, and whether any of
    them IS a brick is a question about their contents."""
    if item.kind == "gauntlet":
        from . import gauntlet as _gauntlet
        _gauntlet.load_bricks(Path(item.options["items_dir"]))


def run(root: Path, target: str, *, workspace: Path,
        seats: "dict[str, str] | None" = None, keep: bool = False,
        launch=None) -> "list[dict]":
    """Run and score every item `target` names. Returns one row each."""
    root = Path(root)
    sets = load(root)
    items = select(sets, target)
    commit = _build.resolve_commit(None)
    base = _build.ensure_base(root, commit)
    if not (base_dir(root) / "asterism.db").is_file() and sets.base_problems:
        raise LabError(
            f"the base at {base_dir(root)} has no asterism.db — its seed "
            f"problems were never initialised. Delete it and re-run so "
            f"`lab build` materialises it again.")
    for item in items:
        preflight(item)
    out_rows: "list[dict]" = []
    for item in items:
        slice_ = (cached_slice(root, workspace=workspace, problem=item.problem)
                  if item.needs_slice else None)
        exp = _experiment(sets, item, seats)
        rep = _build.next_rep(root, EXPERIMENT_NAME, item.arm)
        kwargs = {} if launch is None else {"launch": launch}
        ws = _run.run_once(
            root, exp, item.arm, slice_=slice_, base=base, commit=commit,
            rep=rep, keep=keep, problem=item.problem,
            score=lambda rec, it=item: score(it.kind, it.expected, rec),
            extra={"standard_set": item.set_name,
                   "standard_item": item.name,
                   "expected": item.expected,
                   "expected_from": str(item.expected_path)},
            **kwargs)
        record_path = ws / _run.OUT_DIRNAME / _run.RECORD_BASENAME
        record = json.loads(record_path.read_text(encoding="utf-8"))
        got = record.get("score") or {"ok": False, "checks": {}}
        append_scorecard(root, name=item.name, kind=item.kind, record=record,
                         record_path=record_path, expected=item.expected,
                         score=got)
        print(f"[standard] {item.name:<32} {item.kind:<15} "
              f"{'ok' if got['ok'] else 'FAIL'}  {_got_cell(got)}  "
              f"-> {record_path}", flush=True)
        out_rows.append({"item": item.name, "kind": item.kind,
                         "score": got, "record_path": str(record_path),
                         "workspace": str(ws)})
    n_ok = sum(1 for r in out_rows if r["score"]["ok"])
    print(f"[standard] {n_ok}/{len(out_rows)} item(s) met their "
          f"expectation — {scorecard_path(root)}", flush=True)
    return out_rows


def runs_root(root: Path) -> Path:
    return runs_dir(root, EXPERIMENT_NAME)
