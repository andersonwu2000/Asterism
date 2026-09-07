"""`<root>/docs/<exp>/lab.yaml` — what an experiment declares.

One file per experiment, beside its `report.md`, in the operator's
development area. It names the slice every arm starts from, the code
commit every arm runs, and one block per arm: which driver, which
prompts replace which, which seats, and the driver's own inputs.

    snapshot: Combinatorics.union_closed@20260902-233100Z
    # ...or, equivalently, the slice to take if it is not there yet:
    rewind: {problem: Combinatorics.union_closed,
             cutoff: "2026-09-02T23:31:00+00:00"}
    code_commit: 300a6e89        # optional; HEAD of the framework repo
    reps: 2                      # optional; `--reps` overrides
    arms:
      baseline:
        kind: judge_round        # the driver
        group: 691
        rows: [1119, 1362]       # programme_revisions ids to re-judge
      rubric_v2:
        kind: judge_round
        group: 691
        rows: [1119, 1362]
        prompts:                 # <path under Tooling/prompts/>: <file>
          adversary/adversary.md: overlays/rubric_v2/adversary.md
        seats:                   # <seat>: provider/model[:effort]
          adversary: codex/gpt-5:xhigh

EVERY KEY IS CHECKED AND AN UNKNOWN ONE IS A REFUSAL. A lab.yaml is
hand-written under time pressure, and the failure it is exposed to is
not a crash: a mistyped `prompt:` for `prompts:` runs the arm against
the unedited prompt while looking like it worked, which is a result
nobody can tell from a real one. The refusals here name the keys the
kind does take, because a message that only says "no" gets worked
around.

Paths in an arm — prompt overlays, a recovered `decision.json`, a push's
prompt file — are resolved RELATIVE TO THE lab.yaml, never to the
framework repo. The lab's inputs live with the lab.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import LabError, docs_dir

#: The five drivers, and the arm keys each one takes beyond the common
#: set. A kind that is not here cannot be spelled in a lab.yaml, which
#: is what stops an arm from silently running the default driver.
DRIVER_KINDS: "dict[str, tuple[str, ...]]" = {
    # One Adversary round on a proposal — a historical one named by
    # `rows:` (`replay_judge`), or one authored as a FILE (`proposal:`,
    # with its `decisions:`), which is what a standard trap is: a scene
    # the record never held, judged against the workspace's own.
    "judge_round": ("group", "rows", "trigger", "decisions", "proposal"),
    # One full Strategist wake: agent -> verify -> judge loop -> commit
    # into this workspace's DB (`replay_strategist`).
    "strategist_wake": ("group", "trigger", "since"),
    # One Theorist wake through the productised pipeline.
    "theory_wake": ("group", "request"),
    # One free-instruction push on the Strategist seat, no verdict.
    "push_wake": ("group", "trigger", "prompt", "prompt2"),
    # The framework's own daemon, in this workspace, on its own port.
    "daemon": ("scope", "stop", "once"),
    # Bare force: N independent Lean bricks, proofs stripped, one shot
    # each on the workspace's formalizer seat, `lake env lean` verdict.
    "gauntlet": ("items_dir",),
}

# The continuity kinds declare their own arm keys beside the code that
# reads them (`lab/continuity.py`), and are merged in here rather than
# spelled twice: a key added to a kind and forgotten in this table is an
# arm that validates against the wrong list and is refused for using the
# option it was written for.
from .continuity import ARM_KEYS as _CONTINUITY_ARM_KEYS  # noqa: E402

DRIVER_KINDS.update(_CONTINUITY_ARM_KEYS)

#: Arm keys every kind takes.
#:
#: `config:` is the third overlay, beside `prompts:` and `seats:`, and
#: it exists because the two that came first cannot express a framework
#: FLAG. A behaviour shipped behind `<section>.<key>` in `Asterism.yaml`
#: — `theorist.rounds`, say — is exactly the kind of thing an arm is
#: for, and without this the only ways to move one were to edit the
#: workspace by hand between build and run (invisible in the record, and
#: `prompt_hashes` exists precisely because that class of edit is
#: invisible) or to fork a prompt file that is not what changed.
_COMMON_ARM_KEYS = ("kind", "prompts", "seats", "config", "notes")

#: What `stop:` may say. `once` (the default) is the daemon's own
#: "exit when the queue empties"; these are the conditions a run that
#: is NOT expected to drain gets stopped on instead.
STOP_KEYS = ("proved", "revisions", "wall_sec")

_TOP_KEYS = ("snapshot", "rewind", "code_commit", "reps", "arms", "notes")


@dataclass(frozen=True)
class Arm:
    """One arm: a driver and everything that arm alone changes."""
    name: str
    kind: str
    #: `<path under Tooling/prompts/>` -> the file that replaces it,
    #: absolute (resolved against the lab.yaml's directory).
    prompts: "dict[str, Path]" = field(default_factory=dict)
    #: `<seat>` -> `provider/model[:effort]`, written into the
    #: workspace's own `Asterism.yaml`.
    seats: "dict[str, str]" = field(default_factory=dict)
    #: `<dotted Asterism.yaml key>` -> value, merged into the
    #: workspace's own `Asterism.yaml` beside the seats.
    config: "dict[str, Any]" = field(default_factory=dict)
    #: The kind's own inputs, already validated for that kind.
    options: dict = field(default_factory=dict)

    def option(self, key: str, default=None):
        return self.options.get(key, default)


@dataclass(frozen=True)
class Experiment:
    name: str
    path: Path
    snapshot: "str | None"
    rewind: "dict | None"
    code_commit: "str | None"
    reps: int
    arms: "dict[str, Arm]"

    @property
    def dir(self) -> Path:
        return self.path.parent

    def arm(self, name: str) -> Arm:
        try:
            return self.arms[name]
        except KeyError:
            raise LabError(
                f"{self.name} has no arm {name!r} — it declares "
                f"{sorted(self.arms)}") from None


def _seat_spec(seat: str, raw: str) -> "dict[str, str]":
    """`provider/model[:effort]` -> the `Asterism.yaml` keys it sets.

    Spelled as one string because that is how a seat is discussed
    ("adversary on codex/gpt-5 at xhigh"), and split HERE rather than in
    the overlay writer so a malformed one is refused while the operator
    is still looking at the file that has it."""
    text = str(raw).strip()
    provider, sep, rest = text.partition("/")
    if not sep or not provider.strip():
        raise LabError(
            f"seat {seat!r}: {raw!r} is not `provider/model[:effort]` "
            f"(e.g. `codex/gpt-5:xhigh`, `claude/claude-fable-5-1`)")
    model, _, effort = rest.partition(":")
    out = {"provider": provider.strip()}
    if model.strip():
        out["model"] = model.strip()
    if effort.strip():
        out["reasoning_effort"] = effort.strip()
    return out


def config_spec(where: str, raw) -> "dict[str, Any]":
    """`{"theorist.rounds": 1}` — checked here, applied by
    `build._apply_overlay`.

    Keys are DOTTED paths into `Asterism.yaml`, spelled the way
    `core.config.get` reads them, so an arm names the flag by the same
    string the production code does and nobody has to translate a
    section/key pair back and forth. A bare key with no dot is refused:
    every knob the framework reads lives under a section, so a dotless
    one is a typo that would land a top-level key nothing ever reads and
    let the arm report green on the setting it meant to change."""
    out: "dict[str, Any]" = {}
    for key, value in dict(raw or {}).items():
        text = str(key).strip()
        if not text or "." not in text or text.startswith(".") \
                or text.endswith(".") or ".." in text:
            raise LabError(
                f"{where}: config key {key!r} is not a dotted "
                f"`<section>.<key>` path into Asterism.yaml (e.g. "
                f"`theorist.rounds: 1`)")
        out[text] = value
    return out


def _refuse_unknown(where: str, got, allowed: "tuple[str, ...]") -> None:
    extra = sorted(set(got) - set(allowed))
    if extra:
        raise LabError(
            f"{where}: unknown key(s) {extra} — this level takes "
            f"{sorted(allowed)}. A mistyped key runs the arm against "
            f"the setting it meant to change and looks like it worked.")


def _parse_arm(name: str, raw: dict, base: Path) -> Arm:
    if not isinstance(raw, dict):
        raise LabError(f"arm {name!r} is not a mapping")
    kind = str(raw.get("kind") or "").strip()
    if kind not in DRIVER_KINDS:
        raise LabError(
            f"arm {name!r}: kind {kind or '(missing)'!r} is not a driver "
            f"— have {sorted(DRIVER_KINDS)}")
    _refuse_unknown(f"arm {name!r}", raw,
                    _COMMON_ARM_KEYS + DRIVER_KINDS[kind])

    prompts: "dict[str, Path]" = {}
    for rel, src in dict(raw.get("prompts") or {}).items():
        path = (base / str(src)).resolve()
        if not path.is_file():
            raise LabError(
                f"arm {name!r}: prompt overlay {src!r} is not a file at "
                f"{path} — overlay paths are relative to the lab.yaml")
        prompts[str(rel).replace("\\", "/").lstrip("/")] = path
    seats = {str(k): _seat_spec(str(k), v)
             for k, v in dict(raw.get("seats") or {}).items()}
    config = config_spec(f"arm {name!r}", raw.get("config"))

    options = {k: raw[k] for k in DRIVER_KINDS[kind] if k in raw}
    _check_options(name, kind, options, base)
    return Arm(name=name, kind=kind, prompts=prompts, seats=seats,
               config=config, options=options)


def _check_options(name: str, kind: str, opts: dict, base: Path) -> None:
    """Per-kind required inputs, refused HERE rather than by the driver.

    A driver that discovers its own inputs are missing has already built
    a workspace, imported a slice and warmed a seat; the operator finds
    out minutes later and pays for the build again."""
    def _need(key: str) -> None:
        if opts.get(key) in (None, "", [], {}):
            raise LabError(f"arm {name!r} ({kind}): `{key}:` is required")

    if kind == "judge_round":
        _need("group")
        check_judge_source(name, opts, base)
    elif kind == "strategist_wake":
        _need("group")
    elif kind == "theory_wake":
        req = opts.get("request") or {}
        if not isinstance(req, dict) or not str(
                req.get("objective") or "").strip():
            raise LabError(
                f"arm {name!r}: `request: {{objective: ..., situation: "
                f"...}}` is required — a Theorist wake is dispatched from "
                f"a Theorize decision, and one with no objective would "
                f"spend an author turn on an empty question")
    elif kind == "push_wake":
        _need("group")
        _need("prompt")
        for key in ("prompt", "prompt2"):
            if opts.get(key):
                p = (base / str(opts[key])).resolve()
                if not p.is_file():
                    raise LabError(
                        f"arm {name!r}: no {key} file at {p}")
                opts[key] = str(p)
    elif kind == "daemon":
        stop = opts.get("stop") or {}
        if stop:
            if not isinstance(stop, dict):
                raise LabError(f"arm {name!r}: `stop:` is a mapping")
            _refuse_unknown(f"arm {name!r} stop", stop, STOP_KEYS)
    elif kind == "gauntlet":
        _need("items_dir")
        opts["items_dir"] = str((base / str(opts["items_dir"])).resolve())
    elif kind in _CONTINUITY_ARM_KEYS:
        from .continuity import check_options as _continuity_check
        _continuity_check(name, kind, opts, base)


def check_judge_source(name: str, opts: dict, base: Path) -> None:
    """A judge round is fed by EXACTLY ONE of `rows:` or `proposal:`.

    `rows:` re-judges what the record holds; `proposal:` judges a file,
    which is the only way to put a scene the record never held in front
    of the judge (a trap: the defect it hides is the measurement, so it
    must not have been written by the seat under test). Both would be
    two proposals under one item's name and the score could not say
    which one the verdict belongs to; neither is no proposal at all.

    Shared by `lab.yaml` and `standard.yaml` — a check spelled twice is
    one that drifts, and the standard sets are the heavier user."""
    rows, proposal = opts.get("rows"), opts.get("proposal")
    if bool(rows) == bool(proposal):
        raise LabError(
            f"{name}: name exactly one proposal — `rows:` (programme_"
            f"revisions ids, one Adversary round each) to re-judge what "
            f"the record holds, or `proposal:` (a file, with its "
            f"`decisions:`) to judge one the record never held")
    if rows is not None and (not isinstance(rows, list)
                             or not all(isinstance(r, int) for r in rows)):
        raise LabError(
            f"{name}: `rows:` is a list of programme_revisions ids "
            f"(integers), one Adversary round each")
    # `proposal:` takes a LIST too, one round each — the same shape
    # `rows:` has always had, and for the same reason: two rounds of one
    # debate are one arm's question, and splitting them across two arms
    # would put the variable under test (whatever the arms differ in)
    # and the round number on the same axis.
    if rows and isinstance(opts.get("decisions"), list):
        raise LabError(
            f"{name}: with `rows:`, `decisions:` is ONE file — the "
            f"override applied to every replayed revision. A list of "
            f"decisions belongs with a list of `proposal:` files")
    # An EMPTY `proposal:` list is already refused above — it is falsy,
    # so it reads as "no proposal at all", which is what it is.
    n_props = len(proposal) if isinstance(proposal, list) else 0
    if isinstance(opts.get("decisions"), list) \
            and len(opts["decisions"]) != n_props:
        raise LabError(
            f"{name}: {len(opts['decisions'])} `decisions:` file(s) for "
            f"{n_props} `proposal:` file(s) — they are paired positionally, "
            f"one decisions.json per proposal, and a mismatch would judge "
            f"a proposal against another round's batch")
    for key in ("proposal", "decisions"):
        raw = opts.get(key)
        if not raw:
            continue
        many = isinstance(raw, list)
        out: "list[str]" = []
        for entry in (raw if many else [raw]):
            path = (base / str(entry)).resolve()
            if not path.is_file():
                raise LabError(
                    f"{name}: no {key} file at {path} — a judge round's "
                    f"inputs are resolved beside the file that names them")
            out.append(str(path))
        opts[key] = out if many else out[0]


def with_seats(exp: Experiment, seats: "dict[str, str]") -> Experiment:
    """`exp` with `seats` merged over every arm's.

    Over, not under: `--seats` is the operator saying "this whole run,
    on this model", and an arm that pinned the same seat pinned it for
    the experiment's own question, not for this one. MERGED rather than
    replacing, so an arm that moves a DIFFERENT seat keeps it — the
    same rule `_apply_overlay` follows against the archived config."""
    if not seats:
        return exp
    over = {str(k): _seat_spec(str(k), v) for k, v in seats.items()}
    return _with_arms(exp, lambda a: {"seats": {**a.seats, **over}})


def with_config(exp: Experiment, config: "dict[str, Any]") -> Experiment:
    """`exp` with `config` merged over every arm's — `--config` is the
    operator saying "this whole run, with this flag", the same way
    `--seats` says "on this model", and it wins over an arm's own for
    the same reason."""
    if not config:
        return exp
    over = config_spec("--config", config)
    return _with_arms(exp, lambda a: {"config": {**a.config, **over}})


def _with_arms(exp: Experiment, patch) -> Experiment:
    """`exp` with `patch(arm)`'s fields replaced on every arm. One
    rebuilder, because `Arm` and `Experiment` are frozen and a second
    hand-written copy of their fields is one that silently drops the
    field added next."""
    arms = {name: Arm(**{"name": a.name, "kind": a.kind,
                         "prompts": a.prompts, "seats": a.seats,
                         "config": a.config, "options": a.options,
                         **patch(a)})
            for name, a in exp.arms.items()}
    return Experiment(name=exp.name, path=exp.path, snapshot=exp.snapshot,
                      rewind=exp.rewind, code_commit=exp.code_commit,
                      reps=exp.reps, arms=arms)


def load(root: Path, exp: str) -> Experiment:
    """Read and validate `<root>/docs/<exp>/lab.yaml`."""
    import yaml

    path = docs_dir(root, exp) / "lab.yaml"
    if not path.is_file():
        raise LabError(
            f"no experiment {exp!r} — expected {path}. An experiment is "
            f"declared by its lab.yaml; `lab` never invents one.")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LabError(f"{path} is not valid YAML: {exc}") from None
    if not isinstance(raw, dict):
        raise LabError(f"{path} must be a mapping at the top level")
    _refuse_unknown(str(path), raw, _TOP_KEYS)

    snapshot = raw.get("snapshot")
    rewind = raw.get("rewind")
    if bool(snapshot) == bool(rewind):
        raise LabError(
            f"{path}: name exactly one slice — `snapshot: <id>` for one "
            f"already taken, or `rewind: {{problem, cutoff}}` for one to "
            f"take at that instant. Both would be two scenes; neither is "
            f"no scene.")
    if rewind is not None:
        if not isinstance(rewind, dict) or not rewind.get("problem") \
                or not rewind.get("cutoff"):
            raise LabError(
                f"{path}: `rewind:` needs `problem:` and `cutoff:` "
                f"(an ISO-8601 instant)")
        rewind = {"problem": str(rewind["problem"]),
                  "cutoff": str(rewind["cutoff"])}

    arms_raw = raw.get("arms") or {}
    if not isinstance(arms_raw, dict) or not arms_raw:
        raise LabError(f"{path}: `arms:` must name at least one arm")
    arms = {str(n): _parse_arm(str(n), a, path.parent)
            for n, a in arms_raw.items()}
    return Experiment(
        name=exp, path=path,
        snapshot=str(snapshot) if snapshot else None,
        rewind=rewind,
        code_commit=(str(raw["code_commit"]) if raw.get("code_commit")
                     else None),
        reps=int(raw.get("reps") or 1), arms=arms)
