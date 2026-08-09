"""The installer's seam onto the provider declarations.

`installer/provider-info.py` is how PowerShell asks Python "how is this
provider installed, how does it authenticate, and can that even be
checked". Its whole reason to exist is that the installer must not
carry a provider branch of its own — `Tooling/llm/capabilities.py` says
why: a name-keyed special case is invisible to the next backend, and
`codex` is coming.

So these tests pin the two halves of that promise: the JSON contract
the PowerShell reads, and the ratchet that keeps the PowerShell from
growing the branch back.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "installer" / "provider-info.py"

#: keys setup-lib.ps1 / setup-orchestrator.ps1 read off the JSON. A
#: rename here is a silently-empty PowerShell variable, which is the
#: failure this list exists to make loud.
_CONTRACT = {"name", "install_method", "install_command", "auth_flow",
             "auth_state", "readiness_argv"}


def _info(provider: str) -> dict:
    p = subprocess.run([sys.executable, str(_SCRIPT), provider],
                       capture_output=True, text=True, cwd=str(_REPO))
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


@pytest.mark.parametrize("provider",
                         ["claude", "antigravity", "gemini", "openai"])
def test_declared_providers_answer_the_whole_contract(provider: str) -> None:
    info = _info(provider)
    assert _CONTRACT <= set(info)
    assert info["name"] == provider


def test_an_unknown_provider_is_an_answer_not_a_crash() -> None:
    """The GPT/codex case, before it exists. `capabilities_for` returns
    an all-undeclared object on purpose, and the installer renders that
    as "you set this one up yourself" — so a new backend needs no
    installer change at all, which is the point."""
    info = _info("codex")
    assert _CONTRACT <= set(info)
    assert info["install_method"] == "undeclared"
    assert info["install_command"] is None
    assert info["auth_state"] == "undeclared"


def test_the_self_managed_choice_is_the_same_shape() -> None:
    """'none' is the page's third radio. It must travel the same road as
    an unknown provider rather than needing its own handling."""
    assert _info("none")["install_method"] == "undeclared"


def test_a_runnable_install_command_is_never_empty() -> None:
    """The installer runs `install_command` whenever `install_method` is
    by_command. The two must not disagree, or setup runs an empty
    PowerShell command and reports success."""
    from Tooling.llm import capabilities as caps
    for name, cap in caps.CAPABILITIES.items():
        if cap.install_method == caps.INSTALL_BY_COMMAND:
            assert cap.install_command, name
        else:
            assert cap.install_command is None, name


def test_an_opaque_account_declares_how_to_probe_it() -> None:
    """auth_state=opaque means no file states the answer, so the only
    honest readiness check is asking the CLI to do something. Without
    `readiness_argv` the installer would have to report "installed" and
    stop — a declaration that hands the unknown back to the caller."""
    from Tooling.llm import capabilities as caps
    for name, cap in caps.CAPABILITIES.items():
        if cap.auth_state == caps.AUTH_STATE_OPAQUE:
            assert cap.readiness_argv, name


def test_the_installer_grows_no_provider_branch() -> None:
    """Ratchet, same move as test_transitions_lint: count the places the
    setup scripts compare against a provider NAME. Display copy is
    allowed to (a human-readable label per provider is not a behaviour
    branch); anything else must read a declared property instead.

    Count above the pin → a behaviour branch appeared: ask the
    declaration, or bump the pin here with the reason.
    """
    # BACKEND names only. 'none' is the page's sentinel for "I'll set
    # this up myself" — a UI value, and there is exactly one of it
    # however many backends exist, so it is not the branch-per-backend
    # this ratchet guards.
    names = ("claude", "antigravity", "gemini", "openai", "codex")
    pattern = re.compile(
        r"\$\w+\s+-(?:eq|ne)\s+'(" + "|".join(names) + r")'", re.IGNORECASE)
    # setup-orchestrator.ps1: ONE — the own_oauth login, whose argv is
    # claude's own knowledge (see the comment at that line). A second
    # own_oauth backend must declare a login argv, not add a name here.
    pinned = {"setup-orchestrator.ps1": 1, "setup-lib.ps1": 0,
              "setup-server.ps1": 0}
    for fname, want in pinned.items():
        text = (_REPO / "installer" / fname).read_text(encoding="utf-8")
        # code only: the prose explaining why NOT to branch on a name
        # says the name, and a lint that reads its own warning as a
        # violation teaches the wrong lesson
        code = "\n".join(re.sub(r"#.*$", "", ln) for ln in text.splitlines())
        got = len(pattern.findall(code))
        assert got == want, (
            f"{fname}: {got} provider-name comparisons, pinned at {want}. "
            f"Read a declared property from capabilities.py instead, or "
            f"bump the pin here with the reason.")
