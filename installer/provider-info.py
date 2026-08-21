"""What the installer needs to know about one LLM provider, as JSON.

The setup orchestrator is PowerShell and the declarations are Python
(`Tooling/llm/capabilities.py`), so this is the seam between them. It
exists so the installer never spells out an install command or an auth
flow of its own: a `if provider -eq 'antigravity'` in PowerShell is the
branch-per-backend that `capabilities.py` was written to stop, and it
would be the one place a new provider (codex/GPT) is forgotten.

Runs AFTER Python and the engine land — lane B's order is Python →
engine → provider, so the declaration is readable by the time the
provider step needs it. Before that the installer only shows the
CHOICE, which is copy, not data.

    python installer/provider-info.py <provider> [--check]

Without --check: the provider's declared properties (what is true of it
on any machine). With --check: also MEASURE this machine — installed,
and ready as far as the provider allows anyone to know. The split is
the module's own line: declaration vs observation, and observation is
never cached.

Exit code is 0 even for an unknown provider: `capabilities_for` returns
an all-undeclared object on purpose, and "nobody wrote this down" is an
answer the installer renders ("you set this one up yourself"), not a
crash.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Tooling.llm import capabilities as caps  # noqa: E402


def _measure(name: str, cap) -> dict:
    """This machine, right now. Never cached, never inferred from the
    declaration — the declaration says what is KNOWABLE, not what is."""
    out: dict = {"installed": False, "exe": None, "ready": None,
                 "detail": "", "identity": None, "identity_path": None}
    exe = None
    if name == "claude":
        from Tooling.llm.claude_cli import resolve_claude_executable
        exe = resolve_claude_executable()
    elif name == "antigravity":
        from Tooling.llm.antigravity_cli import (agy_identity,
                                                 resolve_agy_executable)
        exe = resolve_agy_executable()
        # WHICH account agy will spend. A legacy ~/.gemini/oauth_creds.json
        # outranks the IDE session and NOTHING errors when the wrong one
        # wins — the run just bills a different subscription. The verdict
        # is the engine's (`agy_identity`); the installer only renders it.
        verdict, path = agy_identity()
        out["identity"] = verdict
        out["identity_path"] = str(path) if path else None
    elif cap.exe_name is not None:
        # the DECLARED binary (zen rides codex's) — checked before
        # install_method, since a provider can have nothing of its own
        # to install and still depend on a carrier binary being present
        import shutil
        exe = shutil.which(cap.exe_name)
    elif cap.install_method == caps.INSTALL_NOT_NEEDED:
        # reached over HTTP: there is no binary, and "not installed"
        # would be a lie about something that needs no installing
        exe = ""
    else:
        # Only claude and agy own a resolver (they have install homes a
        # fresh PATH can miss). For the rest the CLI is named after the
        # provider — codex ships `codex`; anything else declares
        # exe_name (branch above). `serve/app.py::_provider_rows`
        # follows the same rule — declared once, consumed twice.
        import shutil
        exe = shutil.which(name)
    out["installed"] = exe is not None
    out["exe"] = exe
    if exe is None:
        return out

    if cap.auth_state == caps.AUTH_STATE_READABLE and name == "claude":
        creds = Path.home() / ".claude" / ".credentials.json"
        out["ready"] = creds.exists()
        out["detail"] = "signed in" if creds.exists() else "not signed in"
        return out

    if cap.readiness_argv:
        # The honest check where the credential state is opaque: ask the
        # CLI to do something that needs the account. It is NECESSARY,
        # not sufficient — nobody has measured how this fails with no
        # credentials at all (testing that costs a real interactive
        # login), so the installer reports what happened, never "signed
        # in".
        try:
            p = subprocess.run([exe, *cap.readiness_argv],
                               capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            out["ready"] = False
            out["detail"] = f"could not run: {e}"
            return out
        ok = p.returncode == 0
        lines = [ln.strip() for ln in (p.stdout or "").splitlines()
                 if ln.strip()]
        out["ready"] = ok
        out["detail"] = (f"reached the service, {len(lines)} models offered"
                         if ok else
                         (p.stderr or p.stdout or "").strip()[:200])
        out["models"] = lines if ok else []
        return out

    out["ready"] = None  # nothing anyone can check from here
    out["detail"] = "no readiness check is declared for this provider"
    return out


def main() -> int:
    name = caps.canonical(sys.argv[1] if len(sys.argv) > 1 else None)
    cap = caps.capabilities_for(name)
    info = {
        "name": name,
        "install_method": cap.install_method,
        "install_command": cap.install_command,
        "auth_flow": cap.auth_flow,
        "auth_state": cap.auth_state,
        "readiness_argv": list(cap.readiness_argv),
    }
    if "--check" in sys.argv[2:]:
        info.update(_measure(name, cap))
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
