"""Manifest.md parser. Best-effort: missing fields → defaults + warning.

Format (see docs/architecture.md §4):
  ---
  problem: <name>
  axioms_whitelist: [...]
  forbidden_lemmas: [...]
  ---
  # <name> — <description>
  ## Statement
  <Lean 4 type expression>
  ## Mathlib hints
  - <hint>
  ## Strategic notes
  <free-form>

Phase 2: dropped `## Entry kind` section. `cli init` now hardwires
root.entry_kind='Backward' (Strategist handles initialisation routing).
Existing Manifest.md files may still carry `## Entry kind` — parser
silently ignores it (treated as unknown section, no warning).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Manifest:
    problem: str
    statement: str
    axioms_whitelist: list[str] = field(default_factory=list)
    forbidden_lemmas: list[str] = field(default_factory=list)
    strategic_notes: str = ""
    # Opt-in: should this Problem's proved decls be Library-ized for
    # cross-problem reuse + mathlib upstreaming (see
    # docs/archive/design/librarian_plan.md). Scope flag, NOT a safety gate —
    # default False so a missing/garbled field never auto-promotes.
    library: bool = False
    # Paper pipeline (docs/internal/paper_pipeline_design.md): shelf id
    # of the source paper (`Papers/<id>/`). Empty = no paper. Drives the
    # Context paper-index section + provenance; never consumed by gates.
    # DEPRECATED as a frontmatter field (2026-07-07): bindings live in
    # the problem_papers table (init migrates this pointer, Scholar/UI
    # bind directly). The slot stays for the legacy dual-read
    # (`context._paper_ids_for` primary derivation) — coordinate before
    # removing.
    paper: str = ""



FRAMEWORK_DEFAULT_AXIOMS: tuple[str, ...] = (
    "Classical.choice", "propext", "Quot.sound",
)
"""The three Lean kernel axioms accepted by default when a Manifest
does not set `axioms_whitelist`. sorryAx is deliberately excluded —
catching it is the entire reason the axiom gates exist. Operators who
need additional axioms (e.g. `native_decide`, `Lean.ofReduceBool`)
must add them explicitly in the Manifest. (SoT moved here from
quality/verify.py — the Manifest owns whitelist semantics; verify
re-exports for back-compat.)"""

_default_axioms_warned: set[str] = set()


def effective_axioms(mfst: "Manifest", *, problem: str = "") -> list[str]:
    """THE derivation of the axiom whitelist every gate consumes.

    An absent/empty Manifest `axioms_whitelist` NEVER weakens a gate —
    it falls back to `FRAMEWORK_DEFAULT_AXIOMS` (with a once-per-problem
    warning so the implicit fallback stays operator-visible). Before
    this helper the empty-field semantics were re-decided at ≥6 call
    sites with THREE different meanings (root gate/harvest: fallback;
    pipeline gates: skip the rogue check entirely; axiom_probe:
    fail-closed) — every new gate author had to pick the right one
    (2026-07-04 convention audit, finding 3)."""
    wl = list(mfst.axioms_whitelist or [])
    if wl:
        return wl
    key = problem or getattr(mfst, "problem", "") or "?"
    if key not in _default_axioms_warned:
        _default_axioms_warned.add(key)
        print(f"[axioms] {key}: Manifest didn't set axioms_whitelist; "
              f"gates use the framework default "
              f"{list(FRAMEWORK_DEFAULT_AXIOMS)}", flush=True)
    return list(FRAMEWORK_DEFAULT_AXIOMS)


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _warn(msg: str) -> None:
    print(f"[manifest] WARN: {msg}", file=sys.stderr)


def _coerce_bool(value: object) -> bool:
    """Frontmatter scalars arrive as strings (`_parse_frontmatter`
    stores `key: val` as the raw string). Accept `true`/`yes`/`1`
    (case-insensitive) as True; everything else — including a missing
    field or unparseable junk — is False. Conservative by design: the
    `library:` opt-in must never default to True on a typo."""
    if isinstance(value, bool):
        return value
    return str(value if value is not None else "").strip().lower() in (
        "true", "yes", "1",
    )


def _parse_yaml_list(value: str) -> list[str]:
    """Parse YAML inline list `[a, b, c]` or block list (one per `- ` line).
    Lightweight, not a full YAML parser."""
    value = value.strip()
    if value.startswith('['):
        inner = value.strip('[]').strip()
        if not inner:
            return []
        return [s.strip().strip("'\"") for s in inner.split(',') if s.strip()]
    return []  # block lists handled by caller


def _parse_frontmatter(text: str) -> dict[str, object]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    body = m.group(1)
    out: dict[str, object] = {}
    current_list_key: str | None = None
    for line in body.splitlines():
        if not line.strip():
            current_list_key = None
            continue
        if line.startswith('  - ') or line.startswith('- '):
            if current_list_key:
                item = line.lstrip(' -').strip().strip("'\"")
                out.setdefault(current_list_key, []).append(item)  # type: ignore
            continue
        if ':' in line and not line.startswith(' '):
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()
            if val == '':
                current_list_key = key
                out[key] = []
            elif val.startswith('['):
                out[key] = _parse_yaml_list(val)
                current_list_key = None
            else:
                out[key] = val.strip("'\"")
                current_list_key = None
    return out


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def _parse_bullet_list(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('- '):
            items.append(line[2:].strip())
    return items


class ManifestCache:
    """Mtime-aware Manifest cache. Each `__getitem__` re-stat's the
    backing Manifest.md and reparses if its mtime has changed since
    the last load. Lets a long-running daemon pick up user edits
    mid-run instead of requiring restart (dispatcher previously had
    no hot-reload — `dispatcher.run` parsed once at startup and
    forever served the cached copy).

    Quack-compatible with `dict[str, Manifest]` for the operations
    the rest of the framework uses: `__getitem__`, `__contains__`,
    `__iter__`, `__len__`, `keys()`, `items()`. Mutation goes through
    `load()` (initial registration at startup or post-init).

    Reload failure (Manifest parse raises after a mid-run edit
    introduced bad syntax) keeps the prior cached entry and logs —
    daemon does not crash on transient bad edits. The mtime cache
    advances so we don't retry-fail every spawn.
    """

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        # problem -> (manifest_path_str, last_mtime, manifest)
        self._entries: dict[str, tuple[str, float, Manifest]] = {}

    def _overlay_db(self, problem: str, mfst: Manifest) -> Manifest:
        """Dual-read (frontmatter dissolve): stamp `problem_settings`
        rows over the freshly-parsed file — state/settings.py owns the
        semantics (present key wins, absent key = file value stands).
        This is the single point where every runtime consumer (gates
        via effective_axioms, prompt assembly, harvest opt-in) gets DB
        values without changing a call site. No DB / no table / any
        read error → the file values stand; a read must never take
        the daemon down or weaken a gate."""
        try:
            from . import db as _db
            from . import settings as _settings
            path = self._workspace / "asterism.db"
            if not path.exists():
                return mfst
            conn = _db.connect_readonly(path)
            try:
                _settings.overlay(mfst, _settings.read(conn, problem))
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 — fallback is the file itself
            pass
        return mfst

    def load(self, problem: str, manifest_path: str) -> Manifest | None:
        """Initial parse. Caller (dispatcher.run startup loop +
        post-init registration paths) supplies the manifest_path
        from `problems.manifest_path`. Returns the parsed Manifest;
        subsequent `cache[problem]` access uses mtime-keyed re-parse
        on top of this baseline.

        Missing file or parse error → log + skip (do not register).
        Defensive: orphan `problems` rows (legitimate-but-no-longer-
        on-disk problem, e.g. manifest dir manually removed) must not
        crash daemon startup. Downstream iteration over
        `manifests.keys()` then naturally omits the skipped problem,
        which leaves any leftover goals/strategies in DB undispatched
        but stable (and surfaceable via `asterism doctor`)."""
        full = self._workspace / manifest_path
        try:
            mtime = _stat_mtime(full)
            mfst = parse(full)
        except (FileNotFoundError, OSError) as e:
            print(f"[manifest-load] {problem} skipped (file missing): "
                  f"{type(e).__name__}: {e}", flush=True)
            return None
        except Exception as e:
            print(f"[manifest-load] {problem} skipped (parse failed): "
                  f"{type(e).__name__}: {e}", flush=True)
            return None
        mfst = self._overlay_db(problem, mfst)
        self._entries[problem] = (manifest_path, mtime, mfst)
        return mfst

    def __getitem__(self, problem: str) -> Manifest:
        entry = self._entries.get(problem)
        if entry is None:
            raise KeyError(problem)
        manifest_path, last_mtime, mfst = entry
        full = self._workspace / manifest_path
        cur_mtime = _stat_mtime(full)
        if cur_mtime == last_mtime:
            # settings edits arrive via the DB with NO file-mtime
            # signal — re-overlay so a UI change hot-reloads exactly
            # like a body edit does (one read-only connect per access;
            # spawn-cadence, not hot-loop)
            return self._overlay_db(problem, mfst)
        try:
            new_mfst = parse(full)
        except Exception as e:
            print(f"[manifest-reload] {problem} parse failed "
                  f"(keeping cached): {type(e).__name__}: {e}",
                  flush=True)
            # Advance mtime so we don't retry-fail every spawn.
            self._entries[problem] = (manifest_path, cur_mtime, mfst)
            return mfst
        new_mfst = self._overlay_db(problem, new_mfst)
        self._entries[problem] = (manifest_path, cur_mtime, new_mfst)
        print(f"[manifest-reload] {problem} (mtime changed)", flush=True)
        return new_mfst

    def __contains__(self, problem: object) -> bool:
        return problem in self._entries

    def __iter__(self):
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def keys(self):
        return self._entries.keys()

    def items(self):
        # Materialize via __getitem__ so callers see fresh manifests.
        return [(p, self[p]) for p in self._entries]


def _stat_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def parse(path: Path) -> Manifest:
    text = path.read_text(encoding='utf-8')
    fm = _parse_frontmatter(text)

    problem = str(fm.get('problem') or path.parent.name)

    body_start = _FRONTMATTER_RE.match(text)
    body = text[body_start.end():] if body_start else text
    sections = _parse_sections(body)

    # Statement section is optional (was required pre-Phase-?). The
    # canonical statement now lives in the hand-written Root.lean theorem
    # signature; cli init extracts it from there. A Manifest may still
    # include `## Statement` as human-readable description, but the
    # framework does not consume it for dispatch.
    statement = sections.get('Statement', '').strip()

    # Phase 2: `## Entry kind` section removed. Strategist handles
    # routing; cli init hardwires root.entry_kind='Backward'. Existing
    # Manifest files carrying `## Entry kind` are tolerated (section
    # silently ignored) — no warning to avoid noise on legacy files.

    # `## Lemma hints` retired (2026-07-08, owner): presearch covers
    # mechanical lemma discovery per-goal and the strategist directive
    # carries curated API steering, so the structured field had no
    # consumer left. A body section with that title is now plain prose
    # — the Strategist still reads it as natural language.
    notes = sections.get('Strategic notes', '').strip()

    axioms = fm.get('axioms_whitelist') or []
    forbidden = fm.get('forbidden_lemmas') or []
    if not isinstance(axioms, list):
        _warn(f"{path} axioms_whitelist not a list; using []")
        axioms = []
    if not isinstance(forbidden, list):
        _warn(f"{path} forbidden_lemmas not a list; using []")
        forbidden = []

    return Manifest(
        problem=problem,
        statement=statement,
        axioms_whitelist=list(axioms),
        forbidden_lemmas=list(forbidden),
        strategic_notes=notes,
        library=_coerce_bool(fm.get('library')),
        paper=str(fm.get('paper') or "").strip(),
    )


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
    # state/manifest.py for the Manifest dataclass via __init__.
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


# ---------------------------------------------------------------------
# Manifest authoring chokepoint (UI settings-vs-NL split)
# ---------------------------------------------------------------------
#
# The UI presents the Manifest as structured settings (frontmatter) +
# a natural-language body. These helpers keep the file the single
# source of truth while letting either half be replaced independently:
# unknown frontmatter keys survive a settings update untouched, and
# the hot-reload ManifestCache picks the write up on the next tick.

#: frontmatter keys the UI owns; anything else round-trips verbatim.
UI_SETTING_KEYS = (
    "axioms_whitelist", "forbidden_lemmas", "library",
)


def split_raw(text: str) -> "tuple[dict[str, object], str]":
    """(frontmatter dict, body text) — inverse-ish of `compose`."""
    fm = _parse_frontmatter(text)
    m = _FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    return fm, body


def compose(fm: "dict[str, object]", body: str) -> str:
    """Serialize frontmatter + body in the same shape
    `_parse_frontmatter` reads (scalars, string lists, booleans)."""
    lines: list[str] = ["---"]
    for key, val in fm.items():
        if isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, list):
            if len(val) == 0:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def update_manifest(workspace: Path, problem: str, *,
                    body: "str | None" = None,
                    settings: "dict[str, object] | None" = None,
                    ) -> "tuple[int, str]":
    """Rewrite Manifest.md replacing the NL body and/or the UI-owned
    settings keys. Preserves every frontmatter key the UI does not own
    (problem:, paper:, future keys). Returns (0, ok) / (1, why)."""
    from . import db as _db
    pdir = _db.problem_dir(workspace, problem)
    path = pdir / "Manifest.md"
    if not path.exists():
        return 1, f"FAIL: {path} not found"
    fm, old_body = split_raw(path.read_text(encoding="utf-8"))
    if settings is not None:
        for key in UI_SETTING_KEYS:
            if key in settings:
                fm[key] = settings[key]
    fm.setdefault("problem", problem)
    new_text = compose(fm, body if body is not None else old_body)
    # sanity: the result must still parse before it replaces the file
    try:
        _parse_frontmatter(new_text)
    except Exception as e:  # noqa: BLE001
        return 1, f"FAIL: rewritten Manifest would not parse: {e}"
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(new_text, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return 0, "OK: Manifest updated (hot-reload picks it up on the next tick)"
