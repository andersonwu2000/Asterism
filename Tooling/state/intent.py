"""state.intent — a problem's user intent, DB-resident.

The Manifest.md retirement (owner surgery, 2026-08-19). A problem's
user-facing definition is two NL values plus machine settings, and all
three live in the DB:

  * **charter** — the goal: the claim/task this problem exists to
    settle. Stored as the TOP group's `groups.charter` row, which makes
    the old equation `charter : sub-group :: Manifest : problem`
    literal instead of a prompt-level patch: every group, the top one
    included, is judged against its charter and nothing else.
  * **word** — the user's standing directives (`problems.user_word`).
    Rendered verbatim into every agent surface at every depth and never
    replaced by any group's charter. The machine reads it and never
    writes it: there is no RequestUserAmend path to the word.
  * **settings** — `problem_settings` rows (axioms_whitelist,
    forbidden_lemmas, library, signoff). An absent key means the
    framework default; there is no file fallback anymore.

Root.lean / Defs.lean stay hand-authored files (the formal ground
truth, pinned in git); their helpers live here too. `charter` / `word`
edits arrive via the serve UI or the `asterism charter` / `asterism
word` CLI — both call the writers below, which append history rows so
the baseline pin moves with every sanctioned change.

History keys: `user_file_history.file` carries the two pseudo-keys
'charter' and 'word' next to the real filenames 'Root.lean' /
'Defs.lean'. The names carry no `.md` suffix on purpose — they are DB
values, not files.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProblemIntent:
    problem: str
    #: The goal — the top group's charter, verbatim.
    charter: str = ""
    #: The user's standing directives, verbatim. Empty = the user has
    #: not spoken beyond the charter.
    word: str = ""
    axioms_whitelist: list[str] = field(default_factory=list)
    forbidden_lemmas: list[str] = field(default_factory=list)
    # Opt-in: should this Problem's proved decls be Library-ized for
    # cross-problem reuse + mathlib upstreaming (see
    # docs/archive/design/librarian_plan.md). Scope flag, NOT a safety gate —
    # default False so a missing/garbled row never auto-promotes.
    library: bool = False
    # Machine channel (benchmark adapters ONLY — never surfaced in the
    # UI): `signoff: false` opts a problem out of the human Ingest
    # sign-off pause, for unattended batch runs. Default True — an
    # absent or garbled row must pause, never skip the human gate.
    signoff: bool = True


FRAMEWORK_DEFAULT_AXIOMS: tuple[str, ...] = (
    "Classical.choice", "propext", "Quot.sound",
)
"""The three Lean kernel axioms accepted by default when a problem
does not set `axioms_whitelist`. sorryAx is deliberately excluded —
catching it is the entire reason the axiom gates exist. Operators who
need additional axioms (e.g. `native_decide`, `Lean.ofReduceBool`)
must add them explicitly in the problem's settings."""

_default_axioms_warned: set[str] = set()


def effective_axioms(intent: "ProblemIntent", *, problem: str = "") -> list[str]:
    """THE derivation of the axiom whitelist every gate consumes.

    An absent/empty `axioms_whitelist` NEVER weakens a gate — it falls
    back to `FRAMEWORK_DEFAULT_AXIOMS` (with a once-per-problem warning
    so the implicit fallback stays operator-visible). Before this
    helper the empty-field semantics were re-decided at >=6 call sites
    with THREE different meanings (2026-07-04 convention audit,
    finding 3)."""
    wl = list(intent.axioms_whitelist or [])
    # Unconditional sorryAx tripwire, whitelist edition (self-audit
    # 2026-07-12 §3-1c): a whitelist CONTAINING sorryAx would neutralize
    # every downstream rogue-axiom comparison — no configuration may
    # authorize an unproven proof. Stripped here at THE derivation
    # chokepoint so every gate inherits it; loud, never silent.
    if "sorryAx" in wl:
        wl = [a for a in wl if a != "sorryAx"]
        print(f"[axioms] {problem or getattr(intent, 'problem', '?')}: "
              f"'sorryAx' in axioms_whitelist IGNORED — sorry can never "
              f"be whitelisted", flush=True)
    if wl:
        return wl
    key = problem or getattr(intent, "problem", "") or "?"
    if key not in _default_axioms_warned:
        _default_axioms_warned.add(key)
        print(f"[axioms] {key}: no axioms_whitelist setting; "
              f"gates use the framework default "
              f"{list(FRAMEWORK_DEFAULT_AXIOMS)}", flush=True)
    return list(FRAMEWORK_DEFAULT_AXIOMS)


#: The user-intent FILES a problem owns (hand-authored Lean, pinned in
#: git); their content history lives in `user_file_history` (baseline
#: at first load, change rows after; see IntentCache._record_history).
#: Both gate the proved-root flip (quality/verify.root_integrity_gate).
#: The retired Manifest.md's slot became the DB pair charter/word —
#: those record history through their writers, not through a file sweep.
USER_INTENT_FILES: tuple[str, ...] = ("Root.lean", "Defs.lean")

#: `user_file_history.file` pseudo-keys for the DB-resident intent
#: values. Kept alongside USER_INTENT_FILES so baseline/repin tooling
#: (`asterism repin`, root_integrity_gate) can enumerate everything
#: the user owns.
DB_INTENT_KEYS: tuple[str, ...] = ("charter", "word")


def _content_sha(body: str) -> str:
    import hashlib
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def user_file_baseline_row(conn, problem: str, file: str):
    """The baseline row (sha + body) a user file / intent key is pinned
    to: the latest `repin`-source row if any (sanctioned change acks —
    operator `asterism repin`, accepted amendments, and charter/word
    writes through the intent writers, which all record the same
    source; the CHECK constraint only admits 'observed'/'repin'), else
    the first-load observation. None = never recorded."""
    row = conn.execute(
        "SELECT sha, body FROM user_file_history"
        " WHERE problem = ? AND file = ? AND source = 'repin'"
        " ORDER BY id DESC LIMIT 1", (problem, file)).fetchone()
    if row is not None:
        return row
    return conn.execute(
        "SELECT sha, body FROM user_file_history"
        " WHERE problem = ? AND file = ?"
        " ORDER BY id ASC LIMIT 1", (problem, file)).fetchone()


def user_file_baseline(conn, problem: str, file: str) -> "str | None":
    """The sha a user file must still match for the problem's proved
    root to verify (see `user_file_baseline_row`). None = never
    recorded — gate treats as no-pin, fail-open with a warning."""
    row = user_file_baseline_row(conn, problem, file)
    return None if row is None else str(row["sha"])


# ---------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------


def read(conn: sqlite3.Connection, problem: str) -> "ProblemIntent | None":
    """The problem's intent, assembled from its three DB homes.

    None iff the `problems` row itself is missing — a registered
    problem always reads (empty charter/word are legal values; the
    doctor surfaces an empty charter as a defect, the runtime does not
    crash on it)."""
    row = conn.execute(
        "SELECT user_word FROM problems WHERE name = ?",
        (problem,)).fetchone()
    if row is None:
        return None
    top = conn.execute(
        "SELECT charter FROM groups WHERE problem = ?"
        " AND parent_group_id IS NULL", (problem,)).fetchone()
    intent = ProblemIntent(
        problem=problem,
        charter=str(top["charter"]) if top is not None else "",
        word=str(row["user_word"] or ""),
    )
    from . import settings as _settings
    _settings.overlay(intent, _settings.read(conn, problem))
    return intent


# ---------------------------------------------------------------------
# Writes (the chokepoints — every sanctioned charter/word change lands
# here, so the history pin moves with the value)
# ---------------------------------------------------------------------


def _record_db_history(conn: sqlite3.Connection, problem: str, key: str,
                       body: str, *, source: str) -> None:
    sha = _content_sha(body)
    last = conn.execute(
        "SELECT sha FROM user_file_history"
        " WHERE problem = ? AND file = ?"
        " ORDER BY id DESC LIMIT 1", (problem, key)).fetchone()
    if last is not None and str(last["sha"]) == sha and source != "repin":
        return
    conn.execute(
        "INSERT INTO user_file_history"
        " (problem, file, sha, body, seen_at, source)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (problem, key, sha, body, _now(), source))


def _now() -> str:
    from . import db as _db
    return _db.now()


def _workspace_of(conn: sqlite3.Connection) -> "Path | None":
    """The workspace = the DB file's parent (v18 precedent); None for
    :memory: connections (tests) — the seed mirror then skips."""
    db_file = ""
    try:
        for _seq, _name, _file in conn.execute("PRAGMA database_list"):
            if _name == "main":
                db_file = _file or ""
    except sqlite3.Error:
        return None
    return Path(db_file).resolve().parent if db_file else None


def set_charter(conn: sqlite3.Connection, problem: str, body: str, *,
                source: str = "repin") -> None:
    """Write the problem's goal (the top group's charter) + history.

    `source='observed'` is the init baseline; every later sanctioned
    write (UI, CLI, accepted RequestUserAmend) records 'repin' so the
    root-integrity pin moves with the change. Raises ValueError when
    the problem has no top group (init creates it first) or the body
    is empty — a problem with no goal is not a state this writer may
    produce."""
    if not str(body).strip():
        raise ValueError("a problem's charter must not be empty")
    cur = conn.execute(
        "SELECT id FROM groups WHERE problem = ?"
        " AND parent_group_id IS NULL", (problem,)).fetchone()
    if cur is None:
        raise ValueError(f"{problem}: no top group — run init first")
    conn.execute(
        "UPDATE groups SET charter = ?, updated_at = ? WHERE id = ?",
        (str(body).strip(), _now(), int(cur["id"])))
    _record_db_history(conn, problem, "charter", str(body).strip(),
                       source=source)
    conn.commit()
    ws = _workspace_of(conn)
    if ws is not None:
        write_seed(conn, ws, problem)


def set_word(conn: sqlite3.Connection, problem: str, body: str, *,
             source: str = "repin") -> None:
    """Write the user's standing directives + history. Empty is legal
    (the user withdrawing all directives is a statement)."""
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        raise ValueError(f"unknown problem {problem!r}")
    conn.execute(
        "UPDATE problems SET user_word = ? WHERE name = ?",
        (str(body).strip(), problem))
    _record_db_history(conn, problem, "word", str(body).strip(),
                       source=source)
    conn.commit()
    ws = _workspace_of(conn)
    if ws is not None:
        write_seed(conn, ws, problem)


# ---------------------------------------------------------------------
# The durable seed (problem.json) — intake + reset-survival mirror
# ---------------------------------------------------------------------

#: `Problems/<p>/problem.json` — the problem's durable definition on
#: disk. `asterism init` / `init-batch` READ it to seed the DB; the
#: intent/settings writers refresh it best-effort after every
#: sanctioned change (proof_store precedent: one chokepoint keeps DB
#: and file a pair, so drift is structurally impossible — nothing else
#: reads or writes it). `asterism reset` wipes the DB rows but leaves
#: user files alone, so re-init restores exactly what the user last
#: authored. Machine format on purpose: no headings, no frontmatter,
#: nothing for a parser to guess at.
SEED_FILENAME = "problem.json"


def seed_path(workspace: Path, problem: str) -> Path:
    from . import db as _db
    return _db.problem_dir(workspace, problem) / SEED_FILENAME


def read_seed(path: Path) -> "dict | None":
    """Parse a problem.json seed. None on missing file; raises on
    unparseable/invalid content (authoring input — fail loud)."""
    import json as _json
    if not path.is_file():
        return None
    data = _json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a JSON object")
    if not str(data.get("charter", "")).strip():
        raise ValueError(f"{path}: 'charter' (the problem's goal) is "
                         f"required and must be non-empty")
    return data


def write_seed(conn: sqlite3.Connection, workspace: Path,
               problem: str) -> None:
    """Mirror the problem's current DB intent into problem.json.
    Best-effort: a file write failure never blocks the DB write that
    triggered it (the DB is the runtime SoT; the seed is the durable
    copy reset/re-init runs on)."""
    import json as _json
    try:
        pi = read(conn, problem)
        if pi is None:
            return
        from . import settings as _settings
        payload: dict = {"problem": problem, "charter": pi.charter}
        if pi.word:
            payload["word"] = pi.word
        stored = _settings.read(conn, problem)
        if stored:
            payload["settings"] = stored
        path = seed_path(workspace, problem)
        if not path.parent.is_dir():
            return
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(_json.dumps(payload, indent=2, ensure_ascii=False)
                       + "\n", encoding="utf-8", newline="\n")
        tmp.replace(path)
    except Exception as e:  # noqa: BLE001 — mirror only, never blocks
        print(f"[intent-seed] {problem}: seed write failed "
              f"({type(e).__name__}: {e})", flush=True)


# ---------------------------------------------------------------------
# The per-problem view the daemon serves to every consumer
# ---------------------------------------------------------------------


class IntentCache:
    """Dict-like `problem -> ProblemIntent` view over the DB.

    Successor of the mtime-keyed ManifestCache: intent lives in the DB
    now, so every `__getitem__` is a fresh read-only DB read (spawn
    cadence, not hot-loop) — a UI/CLI charter or word edit is live on
    the very next access, no file watching involved. Registration
    (`load`) pins WHICH problems this daemon serves; the accessor also
    sweeps the two hand-authored user files (Root.lean / Defs.lean)
    into `user_file_history`, catching any write channel including a
    Bash bypass of the spawn write-deny.
    """

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        self._problems: dict[str, ProblemIntent] = {}
        # (problem, file) -> last recorded content sha (user_file_history
        # write dedup — avoids a DB round-trip per access)
        self._file_shas: dict[tuple[str, str], str] = {}

    def _record_history(self, problem: str) -> None:
        """Append current content of the problem's user-intent FILES
        (Root.lean / Defs.lean, whichever exist) to `user_file_history`
        when it differs from the last recorded sha. Best-effort:
        history must never break intent loading."""
        try:
            from . import db as _db
            conn = None
            pdir = _db.problem_dir(self._workspace, problem)
            for name in USER_INTENT_FILES:
                path = pdir / name
                if not path.is_file():
                    continue
                body = path.read_text(encoding="utf-8")
                sha = _content_sha(body)
                if self._file_shas.get((problem, name)) == sha:
                    continue
                if conn is None:
                    conn = _db.connect(self._workspace / "asterism.db")
                last = conn.execute(
                    "SELECT sha FROM user_file_history"
                    " WHERE problem = ? AND file = ?"
                    " ORDER BY id DESC LIMIT 1", (problem, name)).fetchone()
                if last is None or str(last["sha"]) != sha:
                    conn.execute(
                        "INSERT INTO user_file_history"
                        " (problem, file, sha, body, seen_at, source)"
                        " VALUES (?, ?, ?, ?, ?, 'observed')",
                        (problem, name, sha, body, _db.now()))
                    conn.commit()
                    if last is not None:
                        print(f"[user-file-history] {problem}/{name}: "
                              f"content changed (sha {sha}) — recorded; "
                              f"review/root gate will surface it",
                              flush=True)
                self._file_shas[(problem, name)] = sha
            if conn is not None:
                conn.close()
        except Exception as e:  # noqa: BLE001 — never break loading
            print(f"[user-file-history] {problem}: record failed "
                  f"({type(e).__name__}: {e})", flush=True)

    def _read(self, problem: str) -> "ProblemIntent | None":
        try:
            from . import db as _db
            path = self._workspace / "asterism.db"
            if not path.exists():
                return None
            conn = _db.connect_readonly(path)
            try:
                return read(conn, problem)
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            print(f"[intent-read] {problem} failed "
                  f"({type(e).__name__}: {e})", flush=True)
            return None

    def load(self, problem: str) -> "ProblemIntent | None":
        """Register `problem` and return its intent, or None (+ log)
        when the DB has no such problem — a legitimate-but-gone row
        must not crash daemon startup; downstream iteration over
        `keys()` then naturally omits it."""
        intent = self._read(problem)
        if intent is None:
            print(f"[intent-load] {problem} skipped (no DB row)",
                  flush=True)
            return None
        self._record_history(problem)
        self._problems[problem] = intent
        return intent

    def __getitem__(self, problem: str) -> ProblemIntent:
        if problem not in self._problems:
            raise KeyError(problem)
        self._record_history(problem)
        fresh = self._read(problem)
        if fresh is None:
            # DB transiently unreadable — serve the last good copy
            # rather than taking the daemon down.
            return self._problems[problem]
        self._problems[problem] = fresh
        return fresh

    def __contains__(self, problem: object) -> bool:
        return problem in self._problems

    def __iter__(self):
        return iter(self._problems)

    def __len__(self) -> int:
        return len(self._problems)

    def keys(self):
        return self._problems.keys()

    def items(self):
        # Materialize via __getitem__ so callers see fresh intents.
        return [(p, self[p]) for p in self._problems]


# ---------------------------------------------------------------------
# Root.lean statement extraction
# ---------------------------------------------------------------------

#: `theorem main : <stmt> := by sorry` — the hand-authored Root.lean
#: contract shape. Single SoT for statement extraction: cmd_init
#: (goals.statement), amend (statement sync), and the root gate's
#: statement pin (task #120) must all read the same bytes. Lazy match
#: is safe here because `:= by sorry` anchors the end of the type
#: expression; a leading `@[instance]`/attribute sits outside the match.
ROOT_STMT_STUB_RE = re.compile(
    r"theorem\s+main\s*:\s*(.+?)\s*:=\s*by\s+sorry\b",
    re.DOTALL,
)


def extract_root_statement(text: str) -> "str | None":
    """Return the type-expression string from Root.lean's
    `theorem main : <stmt> := by sorry`, stripped of surrounding
    whitespace. Returns None if no matching declaration is present."""
    m = ROOT_STMT_STUB_RE.search(text)
    return None if m is None else m.group(1).strip()


# ---------------------------------------------------------------------
# Defs.lean `open` clause propagation
# ---------------------------------------------------------------------

# Top-level `open X Y Z` clauses in Defs.lean. Scope-limited
# `open X in <decl>` forms are intentionally excluded — they belong to
# a specific declaration and do not propagate to other files; only
# file-level opens are part of the problem's shared notation surface.
_DEFS_OPEN_RE = re.compile(r'^open\s+(.+?)\s*$', re.MULTILINE)


def _scoped_open(line: str) -> bool:
    """`open X in ...` (scope-limited to a single declaration) — not
    a file-level open, exclude from propagation."""
    return bool(re.search(r'\bin\b\s*$', line.strip()))


def defs_opens(workspace: Path, problem: str) -> list[str]:
    """Return the list of `open ...` clause arguments declared at file
    scope in `Problems/<problem>/Defs.lean`.

    Each entry is the raw text following `open ` (e.g. `'BigOperators
    Real Nat Topology Rat'` for a single-line multi-namespace open).
    Returns an empty list if Defs.lean is absent or has no top-level
    opens.

    `open X in <decl>` scope-limited forms are excluded — they belong
    to a specific declaration in Defs.lean, not the file's exported
    notation surface.
    """
    # Import here to avoid a circular import: state/db.py imports
    # state/intent.py for the ProblemIntent dataclass via __init__.
    from . import db
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if not defs_path.exists():
        return []
    text = defs_path.read_text(encoding="utf-8")
    out: list[str] = []
    for m in _DEFS_OPEN_RE.finditer(text):
        # The regex captures up to end-of-line, so the match line for
        # an `open X in ...` form has the trailing `in` token visible
        # in the captured group.
        captured = m.group(1).strip()
        if re.search(r'\bin\b\s*$', captured):
            continue
        out.append(captured)
    return out


def defs_namespaces(workspace: Path, problem: str) -> list[str]:
    """File-scope `namespace ...` paths declared in Defs.lean, in the
    same raw-arg shape as `defs_opens` entries. The validation unit
    opens these so a bare snippet resolves Defs symbols (`f`,
    `<problem>_solution`, …) the way the committed namespace-wrapped
    file does (07-18 ×3 + 07-19 ×9: bogus "unknown identifier" on
    content that elaborates clean in the live file). Extracted from
    the file, not assumed — a Defs without a namespace yields [] and
    nothing is opened. Absent Defs → []."""
    from . import db
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    if not defs_path.exists():
        return []
    text = defs_path.read_text(encoding="utf-8")
    return re.findall(r"(?m)^namespace\s+([\w.]+)", text)


def inject_defs_opens(
    content: str, *, problem: str, workspace: Path,
) -> str:
    """Inject any file-level `open ...` clauses from Defs.lean that are
    not already present in `content`. Idempotent — exact-string match
    against `^open <args>$` lines so re-running on already-injected
    content is a no-op.

    Lean 4's `import` does not propagate `open` clauses across files,
    so every agent-authored proof file (sub-goal stubs, strategy
    patches, Builder leaf proofs) must replay Defs.lean's opens to
    avoid silently auto-binding shorthand names like `π` / `Real.sin`
    as implicit parameters — a class of bug responsible for the four
    miniF2F-Valid mid-run repairs aime_1997_p11 / imo_1965_p1 /
    imo_1966_p4 / imo_1962_p4.

    Insertion point: between the last existing `import` line and the
    first `namespace` line; falls back to file head if neither is
    present. New opens are emitted one per line in the order they
    appear in Defs.lean.
    """
    needed_all = defs_opens(workspace, problem)
    if not needed_all:
        return content
    existing = {m.group(1).strip()
                for m in _DEFS_OPEN_RE.finditer(content)
                if not _scoped_open(m.group(0))}
    missing = [o for o in needed_all if o not in existing]
    if not missing:
        return content

    block_lines = [f"open {o}" for o in missing]

    # Insertion point: right after the last `import` line, with one
    # blank line above and below — matches the cmd_init Root.lean
    # template shape (`import ...\n\nopen ...\n\nnamespace ...`).
    lines = content.split("\n")
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            last_import_idx = i
    if last_import_idx < 0:
        # No imports — prepend the open block to file head.
        return "\n".join(block_lines) + "\n\n" + content

    before = lines[: last_import_idx + 1]
    after = lines[last_import_idx + 1 :]
    # Drop leading blank lines from `after` so the injected block
    # carries its own one-blank-line separation (no double blanks).
    while after and after[0].strip() == "":
        after.pop(0)
    return (
        "\n".join(before) + "\n\n"
        + "\n".join(block_lines) + "\n\n"
        + "\n".join(after)
    )
