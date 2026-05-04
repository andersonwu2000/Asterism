"""Manifest.md parser. Best-effort: missing fields → defaults + warning.

Format (see docs/architecture.md §3):
  ---
  problem: <name>
  axioms_whitelist: [...]
  forbidden_lemmas: [...]
  ---
  # <name> — <description>
  ## Statement
  <Lean 4 type expression>
  ## Entry kind
  Builder | Backward
  ## Mathlib hints
  - <hint>
  ## Strategic notes
  <free-form>

`## Entry kind` controls the dispatcher's first worker for the root goal:
`Builder` for leaf-shaped statements (rare; tactic_try + one-shot patch
might close the whole problem), `Backward` for everything that needs
decomposition. Replaces the legacy `## Difficulty 1-10` field; the
boolean directive is the only signal `cli init` actually consumed.
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
    entry_kind: str = "Backward"
    axioms_whitelist: list[str] = field(default_factory=list)
    forbidden_lemmas: list[str] = field(default_factory=list)
    # F49 — `lemma_hints` unifies Mathlib + Library hint paths. Entries
    # like `Mathlib.NumberTheory.ZMod.Basic` and `Library.NumberTheory.
    # wilson` flow through the same `lemma_lookup` (lake env lean
    # `#check`). For backward compat the legacy `## Mathlib hints`
    # section + `mathlib_hints` field are still populated; agents see
    # both unified into `lemma_hints` (see property below).
    lemma_hints: list[str] = field(default_factory=list)
    mathlib_hints: list[str] = field(default_factory=list)
    strategic_notes: str = ""

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


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _warn(msg: str) -> None:
    print(f"[manifest] WARN: {msg}", file=sys.stderr)


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


def parse(path: Path) -> Manifest:
    text = path.read_text(encoding='utf-8')
    fm = _parse_frontmatter(text)

    problem = str(fm.get('problem') or path.parent.name)

    body_start = _FRONTMATTER_RE.match(text)
    body = text[body_start.end():] if body_start else text
    sections = _parse_sections(body)

    statement = sections.get('Statement', '').strip()
    if not statement:
        _warn(f"{path} missing ## Statement section")

    entry_kind_str = sections.get('Entry kind', 'Backward').strip()
    if entry_kind_str in ('Builder', 'Backward'):
        entry_kind = entry_kind_str
    else:
        _warn(
            f"{path} ## Entry kind unrecognized {entry_kind_str!r}; "
            f"using 'Backward' (Builder|Backward expected)"
        )
        entry_kind = "Backward"

    # F49 — read both `## Lemma hints` (canonical) and `## Mathlib hints`
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
        entry_kind=entry_kind,
        axioms_whitelist=list(axioms),
        forbidden_lemmas=list(forbidden),
        lemma_hints=lemma_hints,
        mathlib_hints=mathlib_hints,
        strategic_notes=notes,
    )
