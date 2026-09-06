"""The LaTeX toolchain, discovered and driven — one answer for two
callers.

`serve/tex_render.py` compiles a document for the Documents panel;
`knowledge/mcp_tools.tex_check` compiles one the Assistant wrote, before
it hands it over. Both need the same four things — which engine is on
this machine, what its command line is, where its log said it broke, and
how many pages came out — and a second copy of any of them is a second
answer to "does this box have TeX".

THE ENGINE IS DISCOVERED AT CALL TIME, never at import. This
installation runs on machines that have TeX (a Windows box with TinyTeX)
and on machines that do not, and the same process may gain one while it
is up. `shutil.which` on each call is cheap and is the only answer that
is true when it is given; an absent engine is not an error but a FACT
the caller states.

Nothing here writes into a Project. A build gets a directory of its
own, the source is copied into it under one fixed name, and the
document's own folder joins `TEXINPUTS` so a sibling `\\input` still
resolves without the build being able to write back through it.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

#: What every build is called inside its own directory. One name, so
#: the log, the pdf and the source are found without parsing anything.
JOBNAME = "main"

#: The engines this module knows, in the owner's preference order.
#: `latexmk` runs the document to a fixed point itself (references,
#: toc); bare `pdflatex` does not, so it is run TWICE; `tectonic` is
#: the self-contained fallback for a machine with no TeX distribution.
ENGINES = ("latexmk", "pdflatex", "tectonic")

#: Said once, here, so every surface and its test cannot drift on it.
NO_ENGINE_DETAIL = (
    "no LaTeX engine on this machine — install TeX Live, MiKTeX or "
    "TinyTeX (the console looks for "
    + ", ".join(ENGINES) + " on PATH each time you ask)")

#: A document that has not finished in this long is not going to. TeX
#: waits for input forever on some errors even under `nonstopmode`.
#:
#: 120 → 300 (2026-09-06). Measured on this box: a WARM latexmk run of a
#: 43 kB article is 0.3–0.7 s, but the first run of the afternoon took
#: 228 s before pdfTeX had even started (`main.tex` written 21:44:24.678,
#: the log's own header `6 SEP 2026 21:48`) — a cold TinyTeX start pays
#: for perl and the kpathsea database once, and the 120 s box fired in
#: the middle of it. 300 s is that cold start with room to spare, and it
#: still fits inside the Assistant turn's 600 s idle deadline, which is
#: the real ceiling: a tool call is SILENCE on that stream.
#: `tests/test_serve_chat.py::test_the_tex_box_fits_inside_the_turn_that_
#: waits_for_it` pins the order of the three clocks.
TIMEOUT_SEC = 300

#: After the box fires the tree is already terminated; this is how long
#: its pipes get to reach EOF before the log is read without them. Not a
#: second time box — a floor against a handle that outlives its process.
_REAP_GRACE_SEC = 10

#: How much of the log a caller is handed. The interesting line is at
#: the END of a TeX log, always.
LOG_TAIL_LINES = 60
LOG_TAIL_CHARS = 6000

#: How many error lines are worth reading before the first one has to
#: be fixed anyway.
MAX_ERRORS = 20


def find_engine() -> "tuple[str, str] | tuple[None, None]":
    """(name, absolute path) of the first engine on PATH, or (None,
    None). Looked up on every call — see the module header."""
    for name in ENGINES:
        exe = shutil.which(name)
        if exe:
            return name, exe
    return None, None


def commands(name: str, exe: str) -> "list[list[str]]":
    """The runs one compile takes. The flags are the owner's: never stop
    for input, and stop at the first real error rather than limping to a
    pdf nobody should trust. `-file-line-error` is what turns TeX's
    `! message` into `file:line: message`, which is the only form a
    reader — or a model — can act on without counting lines."""
    if name == "tectonic":
        # tectonic has no interaction modes: it never prompts, and it
        # keeps its own bundle, so one run is the whole build
        return [[exe, f"{JOBNAME}.tex"]]
    common = ["-interaction=nonstopmode", "-halt-on-error",
              "-file-line-error"]
    if name == "latexmk":
        return [[exe, "-pdf", *common, f"{JOBNAME}.tex"]]
    # pdflatex resolves references on the SECOND pass; one run leaves
    # every \ref reading "??"
    return [[exe, *common, f"{JOBNAME}.tex"]] * 2


def log_text(build: Path, stdout: str) -> str:
    """The engine's own log, or what it printed when it wrote none (a
    toolchain that died before opening the file)."""
    try:
        text = (build / f"{JOBNAME}.log").read_text(encoding="utf-8",
                                                    errors="replace")
    except OSError:
        text = ""
    return text if text.strip() else (stdout or "")


def log_tail(build: Path, stdout: str) -> str:
    """The end of it, clipped to what a panel can show."""
    text = log_text(build, stdout)
    lines = text.splitlines()[-LOG_TAIL_LINES:]
    return "\n".join(lines)[-LOG_TAIL_CHARS:]


#: `./main.tex:12: Undefined control sequence.` — what `-file-line-error`
#: writes. The leading `./` is TeX's, not the author's.
_FILE_LINE = re.compile(r"^\.?[/\\]?(?P<file>[^:\n]+?):(?P<line>\d+): "
                        r"(?P<msg>.+)$")
#: The un-located form, for an engine or a failure mode that writes no
#: file:line at all. Dropping these would report "no errors" on a build
#: that plainly failed.
_BANG = re.compile(r"^! (?P<msg>.+)$")


def error_lines(log: str, *, as_name: str) -> "list[str]":
    """`file:line: message`, one per problem, in the order TeX hit them.

    `as_name` replaces the build copy's `main.tex`: the reader wrote
    `user/paper.tex`, and an error at a line of a file they have never
    seen is an error they have to translate first. A sibling the
    document `\\input`s keeps its own name — it IS a different file.
    """
    out: "list[str]" = []
    seen: "set[str]" = set()
    for raw in log.splitlines():
        line = raw.rstrip()
        m = _FILE_LINE.match(line)
        if m is not None:
            name = m.group("file")
            if Path(name).name == f"{JOBNAME}.tex":
                name = as_name
            row = f"{name}:{m.group('line')}: {m.group('msg')}"
        else:
            m = _BANG.match(line)
            if m is None:
                continue
            row = f"{as_name}: {m.group('msg')}"
        if row in seen:
            continue
        seen.add(row)
        out.append(row)
        if len(out) >= MAX_ERRORS:
            break
    return out


#: `Output written on main.pdf (3 pages, 12345 bytes).`
_PAGES = re.compile(r"Output written on \S+ \((\d+) pages?", re.I)


def page_count(log: str) -> "int | None":
    """How many pages came out, per the engine's own log. None where it
    did not say — a guess would be worse than the silence."""
    m = _PAGES.search(log)
    return int(m.group(1)) if m is not None else None


def _kill_tree(proc: "subprocess.Popen") -> None:
    """Fallback reaper for a child the Job Object never took (an OS that
    refused it, or a platform that has none). `taskkill /T` walks the
    LIVE parent-child chain, which is enough here: the box fires while
    the tree is still attached."""
    if os.name == "posix":
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
        except OSError:
            pass
    else:
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           timeout=_REAP_GRACE_SEC)
            return
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        proc.kill()
    except OSError:
        pass


def _run_boxed(cmd: "list[str]", *, cwd: str, env: "dict[str, str]",
               timeout_sec: int) -> "tuple[int | None, str, bool]":
    """One engine run inside a kill-on-close Job Object, so the time box
    reaps the WHOLE tree. Returns `(returncode, output, timed_out)`;
    `returncode` is None when the box fired.

    `subprocess.run(..., timeout=)` cannot do this, twice over — both
    measured 2026-09-06, when a 120 s box took 228 s of wall clock:

      * it reaps the DIRECT child only. `latexmk` on TinyTeX is a
        runscript `.EXE` whose real work is a `perl` GRANDCHILD, and
        `pdflatex` is that one's child; killing the wrapper leaves the
        compile running.
      * after the kill, its Windows branch calls `communicate()` with NO
        timeout, and that blocks until every holder of the inherited
        stdout handle exits — i.e. until the survivors finish anyway.

    Job membership survives re-parenting, which `taskkill /T` does not
    (`core/process_group.create_capped_job`, written for the same shape
    of bug in the agent spawns). `_kill_tree` is the fallback where the
    OS refuses the job.
    """
    from . import process_group

    job = process_group.create_capped_job(None)
    reaped = [False]

    def reap() -> bool:
        if reaped[0]:
            return False
        reaped[0] = True
        return process_group.terminate_job(job)

    kw: "dict[str, object]" = ({"start_new_session": True}
                               if os.name == "posix" else
                               {"creationflags":
                                process_group.no_window_creationflags()})
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env,
                                # NEVER the caller's own stdin. This runs
                                # inside the stdio MCP server, where fd 0
                                # is the JSON-RPC pipe with a blocking
                                # read pending on it forever; a child
                                # that inherits it does not start on
                                # win32 at all (2026-09-06, measured).
                                # `mcp_tools.main` fences the process
                                # too — this is the half that is true
                                # for every caller of this module.
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace", **kw)
    except BaseException:
        reap()
        raise
    in_job = process_group.assign_to_job(job, proc)
    try:
        out, err = proc.communicate(timeout=timeout_sec)
        return proc.returncode, (out or "") + (err or ""), False
    except subprocess.TimeoutExpired:
        if not (in_job and reap()):
            _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=_REAP_GRACE_SEC)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return None, (out or "") + (err or ""), True
    finally:
        reap()


class Result:
    """What one compile came to. `status` is `ok`, `failed` or
    `timeout`; the rest is whatever that status has to say."""

    __slots__ = ("status", "engine", "detail", "log", "pdf")

    def __init__(self, status: str, engine: str, *, detail: str = "",
                 log: str = "", pdf: "Path | None" = None) -> None:
        self.status = status
        self.engine = engine
        self.detail = detail
        self.log = log
        self.pdf = pdf


def _clear(build: Path) -> None:
    """Empty the build directory before a run.

    A build directory is REUSED — one per document, keyed on its path —
    so the previous run's `main.log`, `.aux`, `.fls` and `.fdb_latexmk`
    are sitting in it. `log_text` reads whatever log is there, and a run
    that is stopped before it opens its own therefore answers with the
    LAST one: measured 2026-09-06 23:26 local, `tex_check` reported
    `:110: Environment definition* undefined` off a log 90 minutes old,
    against a source whose line 110 the Assistant had already fixed and
    which compiles in 1.6 s. Being told to fix what one has just fixed
    is worse than being told nothing.

    latexmk's own `.fdb_latexmk` cache goes with them, and that is the
    point: a scratch build has to say what THIS source does.
    """
    import shutil

    for entry in build.iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        except OSError:
            pass       # a handle still open on it — the run will overwrite


def compile_into(build: Path, source: str, doc_dir: Path, name: str,
                 exe: str, *, timeout_sec: int = TIMEOUT_SEC) -> Result:
    """Write `source` into `build` as `main.tex` and run `name` over it.

    `build` is the caller's own directory — outside any Project — so
    nothing here can write back into the document's tree. `doc_dir`
    joins the engine's search path only: an `\\input`ed sibling has to
    resolve, and reading it is not writing it.
    """
    build.mkdir(parents=True, exist_ok=True)
    _clear(build)
    pdf = build / f"{JOBNAME}.pdf"
    (build / f"{JOBNAME}.tex").write_text(source, encoding="utf-8",
                                          newline="")
    env = {**os.environ}
    # a trailing separator means "and then the usual places" — drop it
    # and TeX stops finding its own class files
    env["TEXINPUTS"] = (f"{doc_dir}{os.pathsep}"
                        + (os.environ.get("TEXINPUTS") or ""))
    out = ""
    rc = 0
    for cmd in commands(name, exe):
        try:
            code, out, timed_out = _run_boxed(cmd, cwd=str(build), env=env,
                                              timeout_sec=timeout_sec)
        except OSError as e:  # the engine vanished between which() and run
            return Result("failed", name, detail=str(e))
        if timed_out:
            # the log is what it reached before the tree was stopped —
            # a half-finished build that already named its error still
            # names it, and the caller hands that on
            return Result("timeout", name,
                          detail=f"{name} did not finish in {timeout_sec}s",
                          log=log_text(build, out))
        rc = code or 0
        if rc != 0:
            break
    log = log_text(build, out)
    if rc != 0 or not pdf.is_file():
        return Result("failed", name,
                      detail=(f"{name} exited {rc}" if rc
                              else f"{name} wrote no pdf"),
                      log=log)
    return Result("ok", name, log=log, pdf=pdf)
