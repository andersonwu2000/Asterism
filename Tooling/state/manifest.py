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
    # `lemma_hints` unifies Mathlib + Library hint paths. Entries
    # like `Mathlib.NumberTheory.ZMod.Basic` and `Library.NumberTheory.
    # wilson` flow through the same `lemma_lookup` (lake env lean
    # `#check`). For backward compat the legacy `## Mathlib hints`
    # section + `mathlib_hints` field are still populated; agents see
    # both unified into `lemma_hints` (see property below).
    lemma_hints: list[str] = field(default_factory=list)
    mathlib_hints: list[str] = field(default_factory=list)
    strategic_notes: str = ""
    # Opt-in: should this Problem's proved decls be Library-ized for
    # cross-problem reuse + mathlib upstreaming (see
    # docs/archive/design/librarian_plan.md). Scope flag, NOT a safety gate —
    # default False so a missing/garbled field never auto-promotes.
    library: bool = False
    # Paper pipeline (docs/internal/paper_pipeline_design.md): shelf id
    # of the source paper (`Papers/<id>/`). Empty = no paper. Drives the
    # Context paper-index section + provenance; never consumed by gates.
    paper: str = ""

    @property
    def all_hints(self) -> list[str]:
        """Unified hint list. `lemma_hints` first, then any
        `mathlib_hints` not already in `lemma_hints` (dedup preserves
        precedence). Callers needing a single agent-facing list use
        this; the two raw fields stay split for migration tracing."""
        seen: set[str] = set()
        out: list[str] = []
        for h in self.lemma_hints + self.mathlib_hints:
            if h not in seen:
                seen.add(h)
                out.append(h)
        return out


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
            return mfst
        try:
            new_mfst = parse(full)
        except Exception as e:
            print(f"[manifest-reload] {problem} parse failed "
                  f"(keeping cached): {type(e).__name__}: {e}",
                  flush=True)
            # Advance mtime so we don't retry-fail every spawn.
            self._entries[problem] = (manifest_path, cur_mtime, mfst)
            return mfst
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

    # Read both `## Lemma hints` (canonical) and `## Mathlib hints`
    # (legacy alias). Either may be present; if both, lemma_hints wins
    # for the unified `all_hints` view but both raw lists stay tracked.
    mathlib_hints = _parse_bullet_list(sections.get('Mathlib hints', ''))
    lemma_hints = _parse_bullet_list(sections.get('Lemma hints', ''))
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
        lemma_hints=lemma_hints,
        mathlib_hints=mathlib_hints,
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
