"""META.md YAML frontmatter parser (impl §5.0).

parse_meta(problem_dir) -> MetaConfig   -- parse META.md from problem directory
validate_meta(meta)                     -- raise MetaError if axioms not declared

MetaConfig fields:
  problem_name: str | None
  axioms: frozenset[str]   -- REQUIRED; schedule rejects if empty
  models: dict[str, str]   -- optional model tier overrides (architecture §8.3 low two layers)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


class MetaError(Exception):
    """Raised when META.md is missing, malformed, or fails validation."""


@dataclass
class MetaConfig:
    problem_name: str | None = None
    axioms: frozenset[str] = field(default_factory=frozenset)
    models: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# YAML frontmatter extraction
# ---------------------------------------------------------------------------

def _extract_frontmatter(text: str) -> str | None:
    """Return the YAML content between the opening and closing '---' markers.

    Returns None if the file does not start with '---' or has no closing marker.
    """
    if not text.startswith("---"):
        return None
    # Skip the opening marker; find the closing \n---
    rest = text[3:]
    idx = rest.find("\n---")
    if idx == -1:
        return None
    return rest[:idx]


# ---------------------------------------------------------------------------
# Minimal YAML parser
# Supports: top-level string scalars, block lists (- item), flat nested maps.
# No external dependency (pyyaml not in requirements.txt).
# ---------------------------------------------------------------------------

_TOP_KEY_RE = re.compile(r'^([\w.]+):\s*(.*)')
_SUB_KEY_RE = re.compile(r'^\s+([\w.]+):\s*(.*)')


def _parse_yaml_simple(yaml_text: str) -> dict:
    """Parse a restricted YAML subset into a plain dict.

    Recognised constructs:
      key: scalar_value
      key:
        - list_item
      key:
        subkey: scalar_value
    """
    result: dict = {}
    lines = yaml_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Top-level key: no leading whitespace
        if line[0:1].isspace():
            i += 1
            continue

        m = _TOP_KEY_RE.match(line)
        if not m:
            i += 1
            continue

        key = m.group(1)
        inline_val = m.group(2).strip()

        if inline_val:
            result[key] = inline_val
            i += 1
            continue

        # Block value: collect indented child lines
        items: list[str] = []
        nested: dict[str, str] = {}
        i += 1
        while i < len(lines):
            sub = lines[i]
            sub_stripped = sub.strip()

            if not sub_stripped or sub_stripped.startswith("#"):
                i += 1
                continue

            # Non-indented line signals end of block
            if not sub[0:1].isspace():
                break

            if sub_stripped.startswith("- "):
                items.append(sub_stripped[2:].strip())
                i += 1
            else:
                km = _SUB_KEY_RE.match(sub)
                if km:
                    nested[km.group(1)] = km.group(2).strip()
                i += 1

        if items:
            result[key] = items
        elif nested:
            result[key] = nested
        # empty block: omit

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_meta(problem_dir: str | Path) -> MetaConfig:
    """Parse + validate META.md YAML frontmatter from *problem_dir*.

    Per impl §5.0: 未宣告 axioms → META.md 解析失敗、scheduler 拒絕載入。
    parse_meta is a single-stage gate; it raises MetaError on:
      - missing file
      - no frontmatter delimiters
      - axioms field declared as inline list (unsupported by minimal parser)
      - axioms field missing or empty (delegated to validate_meta)
    """
    path = Path(problem_dir) / "META.md"
    if not path.exists():
        raise MetaError(f"META.md not found: {path}")

    text = path.read_text(encoding="utf-8")
    fm = _extract_frontmatter(text)
    if fm is None:
        raise MetaError(f"META.md has no YAML frontmatter (expected '---' delimiters): {path}")

    data = _parse_yaml_simple(fm)

    # Reject inline-list / quoted-string forms with an explicit message rather
    # than silently producing an empty frozenset and surfacing as "axioms missing".
    axioms_raw = data.get("axioms", [])
    if axioms_raw and not isinstance(axioms_raw, list):
        raise MetaError(
            "axioms field must be a YAML block list (one '- name' per line); "
            f"inline lists / scalars are not supported: got {axioms_raw!r}"
        )
    axioms = frozenset(str(a) for a in axioms_raw) if isinstance(axioms_raw, list) else frozenset()

    models_raw = data.get("models", {})
    models: dict[str, str] = models_raw if isinstance(models_raw, dict) else {}

    meta = MetaConfig(
        problem_name=data.get("problem_name"),
        axioms=axioms,
        models=models,
    )
    validate_meta(meta)
    return meta


def validate_meta(meta: MetaConfig) -> None:
    """Raise MetaError if *meta* is invalid.

    Currently enforces: axioms field must declare at least one axiom.
    Exposed as a standalone API for programmatic test fixtures; parse_meta
    calls this internally to enforce single-stage failure per spec §5.0.
    """
    if not meta.axioms:
        raise MetaError(
            "META.md must declare at least one axiom in the 'axioms' field; "
            "no default axiom set is inherited from the framework"
        )
