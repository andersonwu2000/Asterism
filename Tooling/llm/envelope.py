"""The per-spawn capability envelope, in one place.

Every provider hands its agent the same three grants — which tools, which
write roots, which MCP servers — and each renders them in its own dialect
because each CLI reads its rules from somewhere different:

  claude  flags + env, per invocation (`--allowedTools`, `--mcp-config`,
          `ASTERISM_SPAWN_WRITE_ROOTS`). Nothing on disk; two concurrent
          spawns cannot interfere.
  agy     files under the home directory, and nothing else — it has no
          config flag (`agy --help`, probed 2026-08-01) and its own docs
          give exactly two scopes, global and per-plugin
          (`builtin/skills/agy-customizations/docs/mcp_servers.md`). So a
          per-spawn envelope means a per-spawn HOME.
  openai  no tools at all (single-shot fence parsing) — it can host no
          role that needs one, which is a property of the provider, not
          of this module.

The grants themselves are provider-independent, so they are computed
here rather than in each provider. A new backend implements one function:
"render this envelope in my dialect", and MUST fail loudly if it cannot —
the failure mode that cost the most so far was agy silently ignoring a
config written where it does not look, which is indistinguishable from
"this provider has no MCP support" (2026-07-30).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .base import LLMRequest

#: Kinds whose sanctioned edit surface is `Library/` — the librarian
#: family edits it in place. Every other persisted artifact is written by
#: framework code, not by a spawn's tools.
_LIBRARY_EDITING_KINDS = ("librarian", "migrate", "classify", "alias")

# ── Per-seat asterism_tools surface (owner ruling 2026-08-22) ─────────
#
# The `mcp_tools` server used to expose every tool to every seat on the
# MCP-config providers (codex/zen/agy) — observed when a strategist
# called `paper_fetch` directly, mid-wake, before its first batch. The
# ruling: `paper_search`/`paper_fetch` are RATIFIED as strategist
# surface (the Scholar pipeline retires with them), everything else is
# seat-scoped, the same table on every provider, and the NL layer never
# touches a Lean surface (the LSP server rides a separate config that
# only Lean workers receive — `write_tools_mcp_config` vs
# `_write_mcp_config` keeps that separation by construction).
#
# The gate is server-side: `mcp_tools` reads ASTERISM_SEAT from its env
# (written into the server entry by the config writers) and registers
# only this table's tools, so codex, claude, and agy all list the same
# filtered surface. The zen shim additionally refuses to execute any
# call whose name was not declared in the request itself.

_NL_TOOLS = frozenset({"inspect", "write_file", "compute", "loogle",
                       "validate_json"})

#: The console Assistant (HID §1.1's capability matrix, §3.5). It is a
#: seat like any other, which is the point: its capabilities arrive
#: through THIS table and the same MCP server the workers use, not a
#: second permission system that would drift from this one.
#:
#: What it may do, and the reason each line is where it is:
#:   inspect / loogle       reading the workspace and Mathlib — the
#:                          matrix's 可讀 row, already fenced by the
#:                          server's own deny roots
#:   paper_search /         finding papers, and taking one. `FetchPaper`
#:   paper_fetch            retired with the Scholar (§3.3 ruling) and
#:                          the Assistant is what took that errand over,
#:                          so the fetch half belongs to it too (owner
#:                          ruling 2026-09-02): §1.1 lists 找論文 as an
#:                          Assistant capability, and the shelve + bind
#:                          runs through `papers/fetch` — the intake
#:                          chokepoint every other caller uses — not a
#:                          raw DB write, which is the thing the matrix
#:                          forbids.
#:   compute                §1.1 lists it (owner ruling 2026-09-02). Not
#:                          the "execution channel" the matrix bars: the
#:                          sandbox has no filesystem, no network and no
#:                          shell, each call is a fresh process, and
#:                          nothing it prints can establish a claim —
#:                          only the kernel does that. It is arithmetic
#:                          the Assistant would otherwise do in its head
#:                          and get wrong in front of a mathematician.
#:   *_project_doc(s)       its one write surface, and it is `agent/`
#:                          only (state/project_docs enforces the area)
#:   prepare_command        §3.8: it PREPARES; the person confirms
#:   daemon_status          the matrix's daemon 狀態 row, read-only
#: Deliberately absent: `write_file` (writes a worker's attempts dir —
#: a directory the Assistant does not have), `validate_json` (validates
#: a worker's own hand-in), and every act channel there has never been.
_ASSISTANT_TOOLS = frozenset({
    "inspect", "loogle", "paper_search", "paper_fetch", "compute",
    "write_project_doc", "list_project_docs", "read_project_doc",
    "prepare_command", "daemon_status"})

SEAT_ASTERISM_TOOLS: "dict[str, frozenset[str]]" = {
    "strategist": _NL_TOOLS | {"paper_search", "paper_fetch"},
    "adversary": _NL_TOOLS,
    "presearch": _NL_TOOLS,
    "formalizer": _NL_TOOLS,     # intake/mint turns; Lean phase adds
                                 # the lsp server via _write_mcp_config
    "librarian": _NL_TOOLS,
    # The theory layer (theory_wake_design.md §5). The author reads
    # the literature — it is the one seat whose errand is the
    # unknown, and the record is not where the answer is — so it
    # carries the strategist's paper pair. The reviewer does not:
    # it rules on THIS document against the record it was handed,
    # and a judge that goes shopping for its own sources is judging
    # a different packet than the author answered.
    "theorist": _NL_TOOLS | {"paper_search", "paper_fetch"},
    "theory_reviewer": _NL_TOOLS,
    "explainer": _ASSISTANT_TOOLS,
}


def asterism_tools_for(seat: str) -> "frozenset[str]":
    """The seat's tool whitelist; unknown seats fail LOUDLY — a seat
    nobody declared must not inherit the widest surface by accident."""
    try:
        return SEAT_ASTERISM_TOOLS[seat]
    except KeyError:
        raise KeyError(
            f"seat {seat!r} has no declared asterism_tools surface — "
            f"add it to envelope.SEAT_ASTERISM_TOOLS") from None


def seat_of_kind(kind: str) -> str:
    """Pipeline kind → tool-surface seat. The Formalizer's arms and the
    librarian family each share one seat; everything else is itself."""
    if kind in ("forward", "backward", "builder", "mint", "intake",
                "formalizer", "prove", "split"):
        return "formalizer"
    if kind in _LIBRARY_EDITING_KINDS or kind.startswith("cleanup"):
        return "librarian"
    return kind


@dataclass(frozen=True)
class Envelope:
    """What one spawn may do. Paths are absolute.

    write_roots[0] is the attempts sandbox and stays first: deny messages
    point at it as "write here instead"."""
    write_roots: "tuple[Path, ...]"
    mcp_config_path: "Path | None"
    #: Subtrees this spawn may NOT read. See `read_deny_roots`.
    read_deny_roots: "tuple[Path, ...]" = ()
    #: Named subtrees this spawn may read BEYOND its kind's own scope —
    #: the Adversary's `proofs/` and its Project's `_docs/`. It lives
    #: here, in the provider-independent envelope, because the caller's
    #: version
    #: (`LLMRequest.extra_read_dirs`) was rendered by claude and silently
    #: dropped by agy and codex, and on agy a read with no matching allow
    #: is soft-denied, which ENDS THE TURN. Measured 2026-08-15: the
    #: judge read every file in its projection, called `list_dir` on the
    #: proofs directory its own prompt calls "readable in place", and the
    #: CLI shut down 14 ms later — twelve times, ~1.9M input tokens,
    #: surfaced only as `agent_no_output`.
    #:
    #: EXACTLY these directories, never the workspace. The Adversary's
    #: `problem_dir` is its projection on purpose, so `_workspace_of`
    #: returns None on purpose; restoring a workspace-wide read to make
    #: that None go away would hand the judge the live problem dir,
    #: sibling attempts and the author's scratch — the isolation that
    #: fresh-per-round exists to keep.
    read_allow_roots: "tuple[Path, ...]" = ()

    def write_roots_env(self) -> str:
        """`ASTERISM_SPAWN_WRITE_ROOTS` value (spawn_guard's parser)."""
        return os.pathsep.join(str(p) for p in self.write_roots)

    def read_deny_roots_env(self) -> str:
        """`ASTERISM_SPAWN_READ_DENY_ROOTS` value (spawn_guard's parser)."""
        return os.pathsep.join(str(p) for p in self.read_deny_roots)


#: Environment a spawn INHERITS, by explicit allowlist.
#:
#: Not a blocklist, and that is the whole point: a blocklist rots the
#: moment the vendor adds a variable, and this one had already rotted.
#: Verified 2026-08-08 — a daemon started from inside a Claude Code
#: session passes CLAUDECODE, CLAUDE_CODE_SESSION_ID,
#: CLAUDE_CODE_ENTRYPOINT, CLAUDE_CODE_SSE_PORT, CLAUDE_PID and
#: CLAUDE_CODE_CHILD_SESSION down into EVERY spawn, because `spawn_env`
#: inherited everything and `claude_cli` only ever ADDED variables. No
#: harm was ever observed (thousands of spawns), but "daemon started
#: from a clean terminal" and "daemon started from inside an agent
#: session" were two different, invisible configurations — and
#: CLAUDE_CODE_SSE_PORT points at the HOST session's server.
#:
#: The three groups below are, in order: what the OS needs to create a
#: process at all, what the CLIs need to authenticate and reach the
#: network, and what the framework's own children read. Everything else
#: is dropped.
#:
#: Names are matched CASE-INSENSITIVELY on Windows (where the
#: environment block is case-insensitive but arbitrarily cased —
#: `SystemRoot`, `ProgramData`, `COMSPEC` all appear as written by
#: whoever set them) and exactly elsewhere.
_ALLOWED_ENV_NAMES: "frozenset[str]" = frozenset({
    # --- process creation / OS identity ------------------------------
    # Omitting any of these breaks CreateProcess or the CLI in ways that
    # do not name themselves: no SYSTEMROOT and Windows sockets fail to
    # initialise; no PATHEXT and a `.cmd` shim is unlaunchable; no TEMP
    # and every tool that writes a scratch file dies at a random depth.
    "PATH", "PATHEXT", "COMSPEC", "OS",
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "DRIVERDATA",
    "TEMP", "TMP", "TMPDIR",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "ALLUSERSPROFILE", "PUBLIC",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME", "USERNAME",
    "USERDOMAIN", "USERDOMAIN_ROAMINGPROFILE", "LOGONSERVER",
    "COMPUTERNAME", "SESSIONNAME",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_ARCHITEW6432", "PROCESSOR_IDENTIFIER", "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
    "PSMODULEPATH",
    # POSIX equivalents — the daemon is Windows-first but nothing here
    # is Windows-only, and a missing LANG breaks unicode output.
    "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    # --- provider auth + network -------------------------------------
    # Auth is normally a file (~/.claude/.credentials.json, the
    # Antigravity IDE session), but the env route is real and stripping
    # it would look like "the vendor logged me out". Corporate TLS /
    # proxy settings are in the same class: dropping them turns every
    # spawn into an unexplained network failure.
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS", "CLAUDE_CODE_OAUTH_TOKEN",
    # Config LOCATION, not session identity — the CLAUDE_CODE_* names
    # that leak the host session are deliberately absent.
    "CLAUDE_CONFIG_DIR",
    "GOOGLE_API_KEY", "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS", "OPENAI_API_KEY",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
    # --- the framework's own children --------------------------------
    # claude spawns the `asterism_tools` MCP server as a child with THIS
    # environment, and the spawn_guard PreToolUse hook runs the same
    # way; both are `python -m Tooling.…`. PYTHONPATH is re-set
    # explicitly by each provider, the rest keep the interpreter honest.
    "PYTHONPATH", "PYTHONIOENCODING", "PYTHONUTF8",
    "ELAN_HOME", "LEAN_SYSROOT",
})

#: Inherited whole. `ASTERISM_*` is the framework's own namespace: the
#: operator's config overrides (`ASTERISM_<KIND>_MODEL`,
#: `ASTERISM_WORKSPACE`, …) are read by `core/config` inside every
#: framework child, and `ASTERISM_SPAWN_WRITE_ROOTS` is the write fence
#: the spawn_guard hook reads. Dropping the prefix would silently move a
#: configured run onto defaults.
_ALLOWED_ENV_PREFIXES: "tuple[str, ...]" = ("ASTERISM_",)

#: Escape hatch. Set to any non-empty value to restore full inheritance
#: for one daemon (`ASTERISM_SPAWN_ENV_INHERIT_ALL=1`). Intended for
#: exactly one situation: a spawn breaks in a way that smells
#: environmental, and you need to know whether the allowlist is the
#: cause before you spend an hour elsewhere. If it fixes it, the fix is
#: to ADD the missing name above — leaving the hatch on re-opens the
#: host-session leak this allowlist closed.
INHERIT_ALL_ENV = "ASTERISM_SPAWN_ENV_INHERIT_ALL"


def _inherit(base: "dict[str, str]") -> "dict[str, str]":
    """Filter `base` down to the allowlist (case-insensitive on
    Windows, where the same variable appears differently cased
    depending on who set it)."""
    fold = (str.upper if os.name == "nt" else (lambda s: s))
    out: "dict[str, str]" = {}
    for k, v in base.items():
        key = fold(k)
        if key in _ALLOWED_ENV_NAMES or any(
                key.startswith(p) for p in _ALLOWED_ENV_PREFIXES):
            out[k] = v
    return out


def spawn_env(base: "dict[str, str] | None" = None) -> "dict[str, str]":
    """The spawn's environment: an ALLOWLISTED slice of the parent's,
    with THIS interpreter's directory first on PATH.

    Agents are handed shell commands that start with a bare `python`
    (scholar's `python -m Tooling.papers.fetch`, and the allowlist
    patterns that authorize exactly that spelling). A bare name is
    resolved against PATH, and the PATH a spawn inherits is the one the
    operator's shell happened to have when the daemon started — so an
    unrelated venv sitting earlier on it hands the agent an interpreter
    without the framework's dependencies. Observed 2026-08-06: scholar's
    fetch died on `ModuleNotFoundError: fitz` and reported "could not
    retrieve the paper", which reads as a paywall, not as a broken
    environment. Two papers were written off before the real cause
    surfaced.

    The daemon knows which interpreter it is; every child should agree.
    Fixing it here rather than in the prompt keeps the allowlist pattern
    (`Bash(python -m Tooling.papers.fetch *)`) matching the literal the
    agent types — a prompt rewritten to an absolute path would have to
    be kept byte-identical with a permission pattern in another file,
    which is the drift this project has paid for before.

    The ALLOWLIST (see `_ALLOWED_ENV_NAMES`) is the second half: a spawn
    should get the same environment whether the daemon was started from
    a clean terminal or from inside an agent session. Everything the
    framework deliberately sets — the PATH prepend here, PYTHONPATH,
    MAX_THINKING_TOKENS, CLAUDE_CODE_DISABLE_*,
    ASTERISM_SPAWN_WRITE_ROOTS, agy's per-spawn HOME/USERPROFILE — is
    written AFTER this function returns and is therefore untouched by
    the filter.
    """
    src = dict(os.environ if base is None else base)
    env = src if os.environ.get(INHERIT_ALL_ENV, "").strip() else _inherit(src)
    own = str(Path(sys.executable).resolve().parent)
    cur = env.get("PATH", "")
    if cur.split(os.pathsep)[:1] != [own]:
        env["PATH"] = own + (os.pathsep + cur if cur else "")
    return env


#: Operator-private subtrees, named relative to the workspace root. A
#: spawn has no legitimate errand in any of them, and each is a channel
#: for something the run is supposed to derive rather than be handed:
#:
#:   docs/          the operator's own writing — STATUS names how far the
#:                  live problem has got, `operator_lessons.md` and
#:                  `strategy/paper_takeaways.md` carry conclusions
#:                  distilled from the literature. Feeding those to a
#:                  worker is the "文獻不拿來餵答案" line, crossed quietly.
#:   .asterism/     backups (whole DBs of earlier runs of the SAME
#:                  problem), caches, daemon runtime state.
#:   asterism.db    the live run: every goal, decision and dead attempt.
#:
#: `Library/` and the spawn's own Project `_docs/` are deliberately
#: absent — both are surfaces the framework hands out on purpose.
PRIVATE_READ_SUBTREES = ("docs", ".asterism", "asterism.db")


def workspace_of(problem_dir: "Path | None") -> "Path | None":
    """`<workspace>/Problems/<name…>` → `<workspace>`."""
    if problem_dir is None:
        return None
    for parent in Path(problem_dir).parents:
        if parent.name == "Problems":
            return parent.parent
    return None


def project_docs_dir(problem_dir: "Path | None") -> "Path | None":
    """`Problems/<project>/_docs` for the spawn's OWN Project (§3.9) —
    where its papers are, and the only documents tree it may read.

    Derived from the path, not the DB: this runs on the spawn's hot
    path in three providers, and the directory a problem physically
    lives under is the Project it was registered on (§3.1 — a rename
    moves the row, never the folder; the shelf writers resolve the name
    from the DB, so a renamed Project's papers are reached through that
    Project's own directory).

    None when the spawn has no problem_dir under `Problems/` — a grant
    nobody can compute is not a grant, and the Adversary's projection
    deliberately has none."""
    ws = workspace_of(problem_dir)
    if ws is None or problem_dir is None:
        return None
    from ..state.project_docs import ROOT_DIRNAME as _DOCS
    try:
        rel = Path(problem_dir).resolve().relative_to((ws / "Problems").resolve())
    except (ValueError, OSError):
        return None
    if not rel.parts:
        return None
    return ws / "Problems" / rel.parts[0] / _DOCS


def _foreign_problem_dirs(workspace: Path,
                          problem_dir: "Path | None") -> "list[Path]":
    """Every OTHER problem's directory, as deny roots.

    Problems sit at mixed depth (`Problems/sylvester_gallai` and
    `Problems/NumberTheory/cube_e2e` both exist), so this walks the
    ladder from `Problems/` down to the spawn's own directory and denies
    each level's siblings. That shape is forced by agy's precedence:
    deny beats allow GLOBALLY, not most-specific-first (measured
    2026-08-10, probe G — a re-allow two levels inside a denied tree was
    still refused), so "deny Problems/, allow my own" is not expressible
    and the siblings have to be named.

    A spawn with no problem_dir under `Problems/` gets nothing denied
    here rather than everything: the read fence must never be the reason
    a legitimate spawn goes blind (that failure is silent on agy).

    `_docs` is skipped at every level: it is the Project's DOCUMENT root
    (§3.6), not a sibling problem, and since §3.9 the spawn's own papers
    live inside it — denying it would blind a worker on the very files
    its Context section points at. Another Project's `_docs` needs no
    entry of its own: it sits inside that Project's directory, which the
    first level already denies."""
    problems = workspace / "Problems"
    if problem_dir is None or not problems.is_dir():
        return []
    try:
        rel = Path(problem_dir).resolve().relative_to(problems.resolve())
    except (ValueError, OSError):
        return []
    from ..state.project_docs import ROOT_DIRNAME as _DOCS
    out: "list[Path]" = []
    level = problems
    for part in rel.parts:
        try:
            out += [c for c in level.iterdir()
                    if c.name != part and c.name != _DOCS]
        except OSError:
            return out
        level = level / part
    return out


def read_deny_roots(workspace: "Path | None",
                    problem_dir: "Path | None") -> "tuple[Path, ...]":
    """Subtrees no spawn may read, provider-independent.

    Rendered by each backend in its own dialect — agy as `read_file(...)`
    deny rules, claude through `spawn_guard` — because the exposure was
    never agy-specific: `spawn_guard._whitelist()` returns the whole repo
    root, so a claude spawn could read `docs/internal/` and the live DB
    just as freely (#162, 2026-08-10)."""
    if workspace is None:
        return ()
    roots = [workspace / name for name in PRIVATE_READ_SUBTREES]
    roots += _foreign_problem_dirs(workspace, problem_dir)
    return tuple(roots)


def envelope_for(req: LLMRequest, *, library_dir: "Path | None" = None
                 ) -> Envelope:
    """The grants this spawn gets, independent of who will render them."""
    roots: "list[Path]" = [Path(req.attempts_dir)]
    if req.kind in _LIBRARY_EDITING_KINDS and library_dir is not None:
        roots.append(Path(library_dir))
    if req.kind == "paper_index":
        # Its problem_dir IS the paper's own directory on the Project's
        # document shelf, and the agent's contract is to write map.md
        # there (papers/index.py re-stamps the frontmatter).
        roots.append(Path(req.problem_dir))
    problem_dir = Path(req.problem_dir) if req.problem_dir else None
    return Envelope(
        write_roots=tuple(roots),
        mcp_config_path=(Path(req.mcp_config_path)
                         if req.mcp_config_path is not None else None),
        read_deny_roots=read_deny_roots(workspace_of(problem_dir),
                                        problem_dir),
        read_allow_roots=tuple(Path(p)
                               for p in (req.extra_read_dirs or ())),
    )
