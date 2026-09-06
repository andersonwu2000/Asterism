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
TIMEOUT_SEC = 120

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


def compile_into(build: Path, source: str, doc_dir: Path, name: str,
                 exe: str, *, timeout_sec: int = TIMEOUT_SEC) -> Result:
    """Write `source` into `build` as `main.tex` and run `name` over it.

    `build` is the caller's own directory — outside any Project — so
    nothing here can write back into the document's tree. `doc_dir`
    joins the engine's search path only: an `\\input`ed sibling has to
    resolve, and reading it is not writing it.
    """
    build.mkdir(parents=True, exist_ok=True)
    pdf = build / f"{JOBNAME}.pdf"
    try:
        pdf.unlink()
    except OSError:
        pass
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
            r = subprocess.run(cmd, cwd=str(build), env=env,
                               capture_output=True, text=True,
                               timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            return Result("timeout", name,
                          detail=f"{name} did not finish in {timeout_sec}s",
                          log=log_text(build, out))
        except OSError as e:  # the engine vanished between which() and run
            return Result("failed", name, detail=str(e))
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
        if rc != 0:
            break
    log = log_text(build, out)
    if rc != 0 or not pdf.is_file():
        return Result("failed", name,
                      detail=(f"{name} exited {rc}" if rc
                              else f"{name} wrote no pdf"),
                      log=log)
    return Result("ok", name, log=log, pdf=pdf)
