"""Which models this machine can be pointed at, grouped by backend.

Extracted from `serve/app.py` (Assistant redesign §4) because two
surfaces now ask the same question: the settings page's per-seat model
picker, and the Assistant panel's one picker that also decides which
CLI answers the question. A module both can import is the alternative
to `chat.py` importing the whole app factory to reach one function.

What lives here is the READING of the answer: how to ask a backend for
its list, how to parse the shape it replies in, and how to derive a
whole board's seating from the ranking that list carries. WHAT each
backend can run is the backend's own declaration
(`llm/capabilities.models`) — a hand-kept table on this side is the
copy that rots, and on 2026-09-06 it had: four retired claude tiers
offered while the live board ran `claude-opus-5`, and one codex model
named out of seven, with nothing ever asking codex at all.
"""
from __future__ import annotations

from pathlib import Path

#: the probe costs a subprocess, and the settings page polls
_models_memo: "dict[str, object]" = {"at": 0.0, "value": None}


def parse_models(provider: str, out: str) -> "list[str]":
    """A backend's listing, read into a RANKED list of slugs.

    Each provider answers in its own shape, and the shape carries more
    than names — codex's JSON says which models its own picker shows
    (`visibility`) and where the vendor ranks them (`priority`, 1 =
    top), which is the ordering every layer below depends on. Anything
    unreadable returns empty: the caller keeps the declared list rather
    than blanking a picker.
    """
    import json
    if provider == "codex":
        try:
            rows = json.loads(out).get("models") or []
        except (ValueError, AttributeError):
            return []
        listed = [r for r in rows
                  if isinstance(r, dict) and r.get("slug")
                  and r.get("visibility") == "list"]
        listed.sort(key=lambda r: (r.get("priority") is None,
                                   r.get("priority", 0)))
        return [str(r["slug"]) for r in listed]
    if provider == "antigravity":
        # `agy models` prints "<slug>\t<pretty name>"
        live = [ln.split("\t")[0].strip() for ln in out.splitlines()
                if ln.strip() and not ln.startswith(" ")]
        return [m for m in live if m and " " not in m]
    return []


def model_groups(workspace: Path, *, probe: bool = False) -> "list[dict]":
    """Every model a seat may be pointed at, grouped by the backend
    that runs it.

    One picker, not two. A seat's backend is not an independent choice
    — it is implied by the model — so offering both invites them to
    disagree (`provider: codex` with `claude-sonnet-5` is a run that
    dies at its first spawn) and draws one fact twice.

    `probe=False` is the POLLED answer and never spawns anything: the
    settings page is read every minute and a subprocess on that path is
    what the side-effect fence exists to catch (it caught this, and it
    was right). Asking a backend to list its models is an action, on its
    own endpoint, memoized — `source` says which answer you are looking
    at, because a declared list is how a retired model name stays
    pickable, and because a reader deserves to know which of the two
    they are reading.
    """
    import subprocess
    import time as _t
    from ..llm import capabilities as _caps
    from ..core import config as _cfg
    now = _t.monotonic()
    if _models_memo["value"] is not None and \
            now - float(_models_memo["at"]) < 600:
        return _models_memo["value"]  # type: ignore[return-value]
    out: "list[dict]" = []
    for name in sorted(_caps.CAPABILITIES):
        cap = _caps.capabilities_for(name)
        if cap.install_method == _caps.INSTALL_NOT_NEEDED:
            continue  # an HTTP endpoint takes whatever the server serves
        exe = None
        if name == "claude":
            # the one resolver, not `shutil.which`: the installer's PATH
            # edit lands in NEW sessions, so a serve started during the
            # install would otherwise call a present CLI absent
            # (`llm/claude_cli.resolve_claude_executable`, which
            # `app.claude_exe` wraps for the accounts panel)
            from ..llm.claude_cli import resolve_claude_executable
            exe = resolve_claude_executable()
        elif name == "antigravity":
            from ..llm.antigravity_cli import resolve_agy_executable
            exe = resolve_agy_executable()
        else:
            # `which_launchable`, never `shutil.which`: an npm-installed
            # CLI puts a POSIX shell script on PATH beside its `.cmd`,
            # `which` returns the script, and CreateProcess refuses it
            # (`[WinError 193]`). That cost codex its first live spawn
            # on 2026-08-12; here it cost the whole listing, silently —
            # the OSError landed in the keep-the-declared-list guard
            # below and codex reported a declared list on a machine
            # whose CLI answers in 300ms (2026-09-06).
            from ..llm.base import which_launchable
            exe = which_launchable(cap.exe_name or name)
        models = list(_cfg.models_for(name))
        source = "declared"
        argv = cap.models_argv if probe else ()
        if argv and exe:
            try:
                r = subprocess.run([exe, *argv], capture_output=True,
                                   text=True, timeout=30,
                                   encoding="utf-8", errors="replace")
                if r.returncode == 0:
                    live = parse_models(name, r.stdout or "")
                    if live:
                        models, source = live, "probe"
            except (OSError, subprocess.SubprocessError):
                pass  # keep the declared list; never blank the picker
        if models:
            out.append({"provider": name, "models": models,
                        "source": source, "installed": exe is not None})
    if probe:
        _models_memo.update(at=now, value=out)
    return out


# ---------------------------------------------------------------------
# the default board — three layers, seated by RANK
# ---------------------------------------------------------------------

#: The pipeline read as THREE layers, strongest first, with the depth
#: each thinks at. A seat is not chosen one at a time: the theory layer
#: writes mathematics the record does not have, the planning layer
#: decides how the programme runs inside the known, and the formal layer
#: does the volume. That ordering is what "the default model" means, so
#: the console offers one control — which house — and everything below
#: follows from it.
#:
#: The depth applies only where the backend reads one (codex writes
#: `model_reasoning_effort`; claude derives its budget from the wall
#: clock), and `default_seats` writes the key only for those.
LAYERS: "tuple[tuple[str, tuple[str, ...], str], ...]" = (
    ("theory", ("theorist", "theory_reviewer"), "xhigh"),
    ("planning", ("strategist", "adversary"), "high"),
    # every remaining seat — the formal layer is the rest by
    # construction, so a seat added later is seated rather than
    # forgotten
    ("formal", (), "medium"),
)

def house_names() -> "list[str]":
    """The backends the default control chooses between.

    DERIVED, never listed: a house is a vendor that declares it can seat
    the whole pipeline on its own ladder (`capabilities.seats_the_board`
    — three layers, three rungs). A tuple of names here would be a
    second copy of the provider table, which is what goes stale and
    what `test_single_home` refuses. The label a person reads (`gpt` for
    codex) is the console's business, not this module's."""
    from ..llm import capabilities as _caps
    return sorted(n for n, c in _caps.CAPABILITIES.items()
                  if c.seats_the_board)


def series_of(provider: str, model: str) -> str:
    """The SERIES a model slug belongs to — the rung, not the build.

    `claude-opus-5` and `claude-opus-4-8` are one rung of the ladder;
    ranking them as two would push the planning layer onto last
    quarter's build of the same tier. Which dash-token carries the
    series is the vendor's business and is declared per provider
    (`capabilities.model_series_token`); a slug too short to carry one
    is its own series (`gpt-5.5`).
    """
    from ..llm import capabilities as _caps
    at = _caps.capabilities_for(provider).model_series_token
    parts = model.split("-")
    if len(parts) < 2:
        return model
    try:
        return parts[at]
    except IndexError:
        return model


def series_ladder(provider: str, models: "list[str]") -> "list[str]":
    """The provider's series, strongest first — read OFF the list.

    The ranking is data, and this is where that is true rather than
    stated: the order is whatever the catalog came back in (codex's own
    `priority`, or the declared order), so a series above today's top
    appears at the top here and every layer below shifts down one. No
    name is written anywhere for it to be added to."""
    out: "list[str]" = []
    for m in models:
        s = series_of(provider, m)
        if s not in out:
            out.append(s)
    return out


def default_seats(groups: "list[dict]",
                  house: str) -> "dict[str, dict[str, str]]":
    """The whole board, derived from one choice of house.

    Layer 1 takes the house's top series, layer 2 the second, layer 3
    the third; within a series the FIRST model wins, which is the
    newest build of that rung. A house the catalog does not offer
    derives nothing — an empty board is honest, and inventing one would
    seat models this machine cannot run.
    """
    from ..core import config as _cfg
    from ..llm import capabilities as _caps
    group = next((g for g in groups if g.get("provider") == house), None)
    if group is None:
        return {}
    models = [str(m) for m in group.get("models") or []]
    ladder = series_ladder(house, models)
    reads_depth = _caps.capabilities_for(house).reasoning_effort
    named = {s for _, seats, _ in LAYERS for s in seats}
    rest = tuple(s for s in _cfg.UI_SEATS if s not in named)
    out: "dict[str, dict[str, str]]" = {}
    for rank, (_layer, seats, depth) in enumerate(LAYERS):
        if rank >= len(ladder):
            break
        series = ladder[rank]
        model = next(m for m in models if series_of(house, m) == series)
        for seat in (seats or rest):
            row = {"provider": house, "model": model}
            if reads_depth:
                row["effort"] = depth
            out[seat] = row
    return out


def houses(groups: "list[dict]") -> "dict[str, dict[str, dict[str, str]]]":
    """Every house's derived board, for the one control that picks
    between them. Computed from the groups that ANSWERED, so a live
    listing seats the live board rather than the declaration beside
    it."""
    return {h: default_seats(groups, h) for h in house_names()}
