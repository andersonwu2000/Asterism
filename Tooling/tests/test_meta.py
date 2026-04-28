"""Unit tests for Tooling/meta.py.

Coverage:
  - parse_meta: valid YAML frontmatter (axioms-only, full, single axiom, no models)
  - parse_meta: error paths (missing file, no frontmatter, unclosed frontmatter)
  - validate_meta: passes with axioms, raises on empty / default MetaConfig
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from Tooling.meta import MetaConfig, MetaError, parse_meta, validate_meta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_meta(tmp_path: Path, content: str) -> Path:
    meta = tmp_path / "META.md"
    meta.write_text(textwrap.dedent(content), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# parse_meta — valid cases
# ---------------------------------------------------------------------------

class TestParseMetaValid:
    def test_axioms_only(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            axioms:
              - propext
              - Quot.sound
              - Classical.choice
            ---
            # Rest of file
        """)
        meta = parse_meta(tmp_path)
        assert meta.axioms == frozenset(["propext", "Quot.sound", "Classical.choice"])
        assert meta.problem_name is None
        assert meta.models == {}

    def test_full_frontmatter(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            problem_name: sylvester_gallai
            axioms:
              - propext
              - Quot.sound
              - Classical.choice
            models:
              backward.agent: opus
              builder.tactic_llm: sonnet
            ---
        """)
        meta = parse_meta(tmp_path)
        assert meta.problem_name == "sylvester_gallai"
        assert meta.axioms == frozenset(["propext", "Quot.sound", "Classical.choice"])
        assert meta.models == {"backward.agent": "opus", "builder.tactic_llm": "sonnet"}

    def test_single_axiom(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            axioms:
              - propext
            ---
        """)
        meta = parse_meta(tmp_path)
        assert meta.axioms == frozenset(["propext"])

    def test_no_models_key(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            problem_name: foo
            axioms:
              - propext
            ---
        """)
        meta = parse_meta(tmp_path)
        assert meta.models == {}

    def test_problem_name_parsed(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            problem_name: my_problem
            axioms:
              - propext
            ---
        """)
        meta = parse_meta(tmp_path)
        assert meta.problem_name == "my_problem"

    def test_models_partial(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            axioms:
              - propext
            models:
              backward.agent: opus
            ---
        """)
        meta = parse_meta(tmp_path)
        assert meta.models == {"backward.agent": "opus"}

    def test_content_after_closing_marker_ignored(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            axioms:
              - propext
            ---
            # This markdown content should not affect parsing
            Some random text with: colons and - dashes
        """)
        meta = parse_meta(tmp_path)
        assert meta.axioms == frozenset(["propext"])


# ---------------------------------------------------------------------------
# parse_meta — error paths
# ---------------------------------------------------------------------------

class TestParseMetaErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(MetaError, match="not found"):
            parse_meta(tmp_path)

    def test_no_frontmatter_plain_markdown(self, tmp_path):
        _write_meta(tmp_path, """\
            # META

            No YAML frontmatter here, just plain markdown.
        """)
        with pytest.raises(MetaError, match="no YAML frontmatter"):
            parse_meta(tmp_path)

    def test_unclosed_frontmatter(self, tmp_path):
        _write_meta(tmp_path, """\
            ---
            axioms:
              - propext
        """)  # no closing ---
        with pytest.raises(MetaError, match="no YAML frontmatter"):
            parse_meta(tmp_path)

    def test_empty_file(self, tmp_path):
        (tmp_path / "META.md").write_text("", encoding="utf-8")
        with pytest.raises(MetaError, match="no YAML frontmatter"):
            parse_meta(tmp_path)

    def test_parse_meta_raises_on_missing_axioms(self, tmp_path):
        """Spec §5.0 字面：parse_meta 在缺 axioms 時直接 raise（單階段 gate）."""
        _write_meta(tmp_path, """\
            ---
            problem_name: foo
            ---
        """)
        with pytest.raises(MetaError, match="axioms"):
            parse_meta(tmp_path)

    def test_parse_meta_raises_on_empty_axioms_list(self, tmp_path):
        """axioms 宣告為空 block → parse_meta raise（不該 silently 拿 empty frozenset）."""
        _write_meta(tmp_path, """\
            ---
            problem_name: foo
            axioms:
            ---
        """)
        with pytest.raises(MetaError, match="axioms"):
            parse_meta(tmp_path)

    def test_parse_meta_raises_on_inline_list(self, tmp_path):
        """Inline list `axioms: [a, b]` 不該被沉默變空、要顯式報格式錯."""
        _write_meta(tmp_path, """\
            ---
            problem_name: foo
            axioms: [propext, Quot.sound]
            ---
        """)
        with pytest.raises(MetaError, match="block list"):
            parse_meta(tmp_path)


# ---------------------------------------------------------------------------
# validate_meta
# ---------------------------------------------------------------------------

class TestValidateMeta:
    def test_valid_passes(self):
        meta = MetaConfig(axioms=frozenset(["propext"]))
        validate_meta(meta)  # must not raise

    def test_three_axioms_passes(self):
        meta = MetaConfig(axioms=frozenset(["propext", "Quot.sound", "Classical.choice"]))
        validate_meta(meta)

    def test_empty_axioms_raises(self):
        meta = MetaConfig(axioms=frozenset())
        with pytest.raises(MetaError, match="axioms"):
            validate_meta(meta)

    def test_default_metaconfg_raises(self):
        meta = MetaConfig()  # axioms defaults to frozenset()
        with pytest.raises(MetaError):
            validate_meta(meta)
