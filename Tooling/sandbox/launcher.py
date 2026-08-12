"""Child side of the compute sandbox. Runs INSIDE the sandbox venv.

Invoked as `<sandbox python> -B -E launcher.py <workdir>`; the agent's
code arrives on stdin (no argv length limit, no quoting to get wrong —
the stray-file incident that started this whole thread was a Windows
path an unquoted shell ate).

Order is the security property: the audit hook must be installed before
the first byte of agent code runs, and everything the calculator may
legitimately need must be imported BEFORE the hook tightens. Both are
asserted at startup by `selftest()`, and the runner refuses to hand over
code if the assertion fails — a sandbox that silently stopped sandboxing
looks exactly like one that works.

WHAT THIS IS NOT. It is not a security boundary against a determined
escape, and no comment here should be read as claiming one. The boundary
is the process: a separate interpreter with no framework package on its
path, an allowlisted environment with no PATH, and a memory/wall-clock
cap outside. This layer stops the CONVENIENT path — the reach for
`import subprocess` or `open(<some absolute path>)` that a model makes
because that is how it has always worked — and tells it where to go
instead. Known limit, stated rather than papered over: `ctypes` cannot
be kept out (numpy imports it at module load, measured 2026-08-10), so
native code remains reachable to anything that does not emit an audit
event. `ctypes.dlopen` and `ctypes.call_function` DO emit one and are
refused.
"""
from __future__ import annotations

import sys

#: Modules with no place in a calculator. Blocking the IMPORT is the
#: cheap half — a name already in `sys.modules` (ctypes, via numpy)
#: raises no import event at all, which is exactly why the event list
#: below carries the real weight.
BLOCKED_IMPORTS = frozenset({
    "socket", "_socket", "ssl", "subprocess", "_posixsubprocess",
    "urllib", "http", "ftplib", "smtplib", "telnetlib", "xmlrpc",
    "multiprocessing", "webbrowser", "ctypes", "_ctypes",
    "sqlite3", "shutil", "pty", "tty",
})

#: Audit events (PEP 578) that mean the calculator is reaching outside
#: its one job. Raised at the C level, so `__subclasses__` walks and
#: other introspection tricks do not get around them.
BLOCKED_EVENTS = (
    "socket.", "subprocess.", "urllib.", "ftplib.", "smtplib.",
    "os.system", "os.exec", "os.spawn", "os.fork", "os.posix_spawn",
    "os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod",
    "os.link", "os.symlink", "os.truncate", "os.putenv", "os.unsetenv",
    "shutil.", "webbrowser.", "glob.", "pathlib.Path.glob",
    # ctypes' two doors to native code. `import ctypes` cannot be
    # refused (numpy needs it); dlopen/call_function can.
    "ctypes.dlopen", "ctypes.dlsym", "ctypes.call_function",
    "ctypes.set_exception", "ctypes.addressof",
)

_user_phase = False
_read_roots: "tuple[str, ...]" = ()


def _install_hook(read_roots: "tuple[str, ...]") -> None:
    global _read_roots
    _read_roots = read_roots

    def hook(event: str, args) -> None:
        if not _user_phase:
            return
        if event == "import":
            top = (args[0] or "").split(".")[0]
            if top in BLOCKED_IMPORTS:
                raise PermissionError(
                    f"`import {args[0]}` is not available in compute. This "
                    f"tool is a calculator: it has no filesystem, no "
                    f"network and no shell. Put the data you need inline "
                    f"in the code, and read files with `inspect`.")
            return
        if event == "open":
            path, mode = str(args[0]), str(args[1] or "r")
            if any(ch in mode for ch in "wax+"):
                raise PermissionError(
                    "compute cannot write files — return your result on "
                    "stdout with print().")
            if not path.startswith(_read_roots):
                raise PermissionError(
                    f"compute cannot read {path!r}. It has no view of the "
                    f"workspace; use `inspect` to read a file and paste "
                    f"the part you need into the code.")
            return
        if event.startswith(BLOCKED_EVENTS):
            raise PermissionError(
                f"`{event}` is not available in compute — it is a "
                f"calculator with no filesystem, network or shell.")

    sys.addaudithook(hook)


def selftest() -> None:
    """Prove the hook is live before any agent code runs.

    A guard that quietly stopped guarding is the failure this whole
    session has been about, so the sandbox refuses to run rather than
    trust its own installation."""
    checks = (
        ("open outside the read roots",
         lambda: open("/definitely/not/a/read/root/x")),
        ("os.system", lambda: __import__("os").system("echo x")),
    )
    for label, fn in checks:
        try:
            fn()
        except PermissionError:
            continue
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(
                f"compute selftest inconclusive for {label}: "
                f"{type(exc).__name__} instead of PermissionError")
        raise SystemExit(f"compute selftest FAILED: {label} was allowed")


def _force_utf8_streams() -> None:
    """Pin the three std streams to UTF-8 from INSIDE the child.

    The runner is launched with `-E`, which makes CPython ignore every
    `PYTHON*` variable — including the `PYTHONIOENCODING=utf-8` the
    parent sets in its allowlisted environment. So the child fell back
    to the machine's legacy code page (cp950 on the workstation this was
    measured on, 2026-08-12) and BOTH directions broke:

      * stdin decoded the agent's UTF-8 bytes with `surrogateescape`,
        turning one `∨` into three lone surrogates, and `compile()`
        then died with "surrogates not allowed" pointing at THIS file —
        a message with no path back to "your comment had a maths
        symbol in it";
      * `print("α")` died symmetrically on the way out.

    A mathematics framework whose calculator refuses `⊆` is broken for
    its actual users: the first union_closed call of the day was lost
    to a `# fam ∨ P ⊆ fam` comment. Setting it here rather than through
    the environment keeps it true whatever the launch flags do later —
    the env round-trip is what failed."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — a detached stream is not fatal
            pass


def main() -> int:
    _force_utf8_streams()
    workdir = sys.argv[1] if len(sys.argv) > 1 else ""
    # Pre-import everything the calculator is allowed to use, BEFORE the
    # hook tightens: numpy pulls in ctypes at module load, so an import
    # blocklist applied first would refuse numpy itself (measured).
    try:
        import numpy  # noqa: F401
    except Exception:  # noqa: BLE001 — numpy is a convenience, not a dep
        pass
    _install_hook(tuple(
        p for p in (sys.prefix, sys.base_prefix, workdir) if p))
    global _user_phase
    _user_phase = True
    selftest()

    code = sys.stdin.read()
    env = {"__name__": "__main__", "__builtins__": __builtins__}
    try:
        exec(compile(code, "<compute>", "exec"), env)  # noqa: S102
    except PermissionError as exc:
        print(f"\n[compute] refused: {exc}", file=sys.stderr)
        return 3
    except BaseException as exc:  # noqa: BLE001 — report, never mask
        import traceback
        traceback.print_exc()
        return 1 if isinstance(exc, Exception) else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
