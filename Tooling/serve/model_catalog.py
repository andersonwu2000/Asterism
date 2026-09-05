"""Which models this machine can be pointed at, grouped by backend.

Extracted from `serve/app.py` (Assistant redesign §4) because two
surfaces now ask the same question: the settings page's per-seat model
picker, and the Assistant panel's one picker that also decides which
CLI answers the question. A module both can import is the alternative
to `chat.py` importing the whole app factory to reach one function.

Move-only: the memo, the probe policy and the docstring below are what
`app._model_groups` did before the extraction.
"""
from __future__ import annotations

from pathlib import Path

#: How to ASK a backend what it can run. Only agy answers today
#: (`agy models`, ~2.5s, zero tokens); `codex --help` carries `--model`
#: and no listing subcommand, and claude takes any name. This is the
#: third provider fact the console has had to keep on its own side —
#: after install and auth — so it wants declaring (`models_argv`)
#: rather than living here.
_MODELS_ARGV: "dict[str, tuple[str, ...]]" = {"antigravity": ("models",)}

#: the probe costs a subprocess, and the settings page polls
_models_memo: "dict[str, object]" = {"at": 0.0, "value": None}


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
    pickable.
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
            import shutil
            exe = shutil.which(name)
        models = list(_cfg.models_for(name))
        source = "declared"
        argv = _MODELS_ARGV.get(name) if probe else None
        if argv and exe:
            try:
                r = subprocess.run([exe, *argv], capture_output=True,
                                   text=True, timeout=30)
                if r.returncode == 0:
                    # `agy models` prints "<slug>\t<pretty name>"
                    live = [ln.split("\t")[0].strip()
                            for ln in (r.stdout or "").splitlines()
                            if ln.strip() and not ln.startswith(" ")]
                    live = [m for m in live if m and " " not in m]
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
