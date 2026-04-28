"""Unit tests for Tooling.subsystems.dedupe (P3 C20)."""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.subsystems.dedupe import DedupeResult, dedupe


@pytest.fixture
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "asterism.db")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def candidate_lean(tmp_path: Path) -> Path:
    p = tmp_path / "candidate.lean"
    p.write_text("theorem _candidate : 1 + 1 = 2 := by decide\n", encoding="utf-8")
    return p


@pytest.fixture
def two_entries(tmp_path: Path) -> list[dict]:
    e1 = tmp_path / "e1.lean"
    e1.write_text("theorem _e1 : 0 + 0 = 0 := rfl\n", encoding="utf-8")
    e2 = tmp_path / "e2.lean"
    e2.write_text("theorem _e2 : 1 + 1 = 2 := by decide\n", encoding="utf-8")
    return [
        {"id": 1, "lean_path": str(e1)},
        {"id": 2, "lean_path": str(e2)},
    ]


# ---------------------------------------------------------------------------
# DEDUPE_MOCK env hook (test-only) — bypass cache + subprocess
# ---------------------------------------------------------------------------


class TestDedupeMock:
    def test_force_hit_returns_first_entry_id(
        self, candidate_lean, two_entries, monkeypatch
    ) -> None:
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        result = dedupe(candidate_lean, two_entries)
        assert result.outcome == "hit"
        assert result.entry_id == 1
        assert result.from_cache is False

    def test_force_miss_returns_novel(
        self, candidate_lean, two_entries, monkeypatch
    ) -> None:
        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        result = dedupe(candidate_lean, two_entries)
        assert result.outcome == "novel"
        assert result.entry_id is None

    def test_force_timeout_returns_timeout(
        self, candidate_lean, two_entries, monkeypatch
    ) -> None:
        monkeypatch.setenv("DEDUPE_MOCK", "force_timeout")
        result = dedupe(candidate_lean, two_entries)
        assert result.outcome == "timeout"

    def test_force_hit_with_empty_entries_raises(
        self, candidate_lean, monkeypatch
    ) -> None:
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        with pytest.raises(ValueError, match="entries list is empty"):
            dedupe(candidate_lean, [])

    def test_unknown_mock_raises(
        self, candidate_lean, two_entries, monkeypatch
    ) -> None:
        """C18 R3 silent-failure red-line: unknown mock value must raise."""
        monkeypatch.setenv("DEDUPE_MOCK", "bogus_value")
        with pytest.raises(ValueError, match="unknown DEDUPE_MOCK value"):
            dedupe(candidate_lean, two_entries)


# ---------------------------------------------------------------------------
# Mode validation
# ---------------------------------------------------------------------------


class TestModeValidation:
    def test_unknown_mode_raises(self, candidate_lean, two_entries) -> None:
        with pytest.raises(ValueError, match="unknown dedupe mode"):
            dedupe(candidate_lean, two_entries, mode="invalid")


# ---------------------------------------------------------------------------
# Subprocess success paths (lake mocked at subprocess.run level)
# ---------------------------------------------------------------------------


class TestSubprocessSuccess:
    def test_hit_outcome_parsed(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "hit", "entry_id": 2})
        fake.stderr = ""
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            result = dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)
        assert result.outcome == "hit"
        assert result.entry_id == 2

    def test_novel_outcome_parsed(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "novel"})
        fake.stderr = ""
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            result = dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)
        assert result.outcome == "novel"
        assert result.entry_id is None

    def test_elab_failed_returns_novel(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        """Spec §7.1 fix (C20 R3 HIGH-1): elab failure → NOVEL on stdout
        (容錯不報錯), warn to stderr. dedupe.lean now writes the spec-compliant
        novel JSON; the wrapper passes it through as outcome='novel'."""
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "novel"})
        fake.stderr = "warn: candidate elab failed: bad syntax"
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            result = dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)
        assert result.outcome == "novel"
        assert result.entry_id is None


# ---------------------------------------------------------------------------
# Subprocess silent-failure red lines
# ---------------------------------------------------------------------------


class TestSubprocessFailureModes:
    def test_no_json_output_raises(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        """rc != 0 + no parseable JSON → must raise (no silent NOVEL fallback)."""
        fake = MagicMock()
        fake.returncode = 1
        fake.stdout = "lake exited with errors"
        fake.stderr = "module not found"
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            with pytest.raises(RuntimeError, match="no JSON output"):
                dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)

    def test_unknown_result_kind_raises(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "bogus"})
        fake.stderr = ""
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            with pytest.raises(RuntimeError, match="unknown result kind"):
                dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)

    def test_hit_missing_entry_id_raises(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "hit"})  # no entry_id
        fake.stderr = ""
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            with pytest.raises(RuntimeError, match="missing valid entry_id"):
                dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)

    def test_subprocess_timeout_returns_timeout_outcome(
        self, candidate_lean, two_entries, tmp_path
    ) -> None:
        with patch(
            "Tooling.subsystems.dedupe.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="lake", timeout=30.0),
        ):
            result = dedupe(candidate_lean, two_entries, lake_cwd=tmp_path)
        assert result.outcome == "timeout"


# ---------------------------------------------------------------------------
# search_cache integration
# ---------------------------------------------------------------------------


class TestCacheIntegration:
    def test_cache_hit_skips_subprocess(
        self, db, candidate_lean, two_entries, tmp_path
    ) -> None:
        """Pre-write cache row → second call hits cache, no subprocess invoked."""
        # First call writes to cache.
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "hit", "entry_id": 2})
        fake.stderr = ""
        with patch(
            "Tooling.subsystems.dedupe.subprocess.run", return_value=fake
        ) as mock_run:
            r1 = dedupe(candidate_lean, two_entries, conn=db, lake_cwd=tmp_path)
        assert r1.from_cache is False
        assert mock_run.call_count == 1

        # Second call: cache hit; no subprocess.
        with patch(
            "Tooling.subsystems.dedupe.subprocess.run", return_value=fake
        ) as mock_run2:
            r2 = dedupe(candidate_lean, two_entries, conn=db, lake_cwd=tmp_path)
        assert r2.from_cache is True
        assert r2.outcome == "hit"
        assert r2.entry_id == 2
        assert mock_run2.call_count == 0

    def test_cache_miss_then_write(
        self, db, candidate_lean, two_entries, tmp_path
    ) -> None:
        """C20 R3 HIGH-2: cache row must use mode='dedupe' so the C21 mutation
        invalidation hook (`WHERE mode='dedupe'` per spec §2.3) actually
        matches."""
        fake = MagicMock()
        fake.returncode = 0
        fake.stdout = json.dumps({"result": "novel"})
        fake.stderr = ""
        with patch("Tooling.subsystems.dedupe.subprocess.run", return_value=fake):
            dedupe(candidate_lean, two_entries, conn=db, lake_cwd=tmp_path)
        rows = db.execute(
            "SELECT scope, mode, results FROM search_cache"
        ).fetchall()
        assert len(rows) == 1
        scope, mode, results = rows[0]
        assert scope == "dedupe"
        assert mode == "dedupe"  # spec §2.3 line 112; C21 mutation filter target
        payload = json.loads(results)
        assert payload["outcome"] == "novel"

    def test_timeout_not_cached(
        self, db, candidate_lean, two_entries, tmp_path
    ) -> None:
        """Transient timeout outcome must NOT be cached (would poison results)."""
        with patch(
            "Tooling.subsystems.dedupe.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="lake", timeout=30.0),
        ):
            dedupe(candidate_lean, two_entries, conn=db, lake_cwd=tmp_path)
        rows = db.execute("SELECT COUNT(*) FROM search_cache").fetchone()
        assert rows[0] == 0


class TestMockBypassesCache:
    """C20 R3 LOW-5: DEDUPE_MOCK must bypass cache lookup AND cache write."""

    def test_mock_bypasses_cache_lookup(
        self, db, candidate_lean, two_entries, tmp_path, monkeypatch
    ) -> None:
        """Pre-write a cache row that says hit→entry_id=2; with mock active,
        the mock's force_miss must win (proving cache lookup is bypassed)."""
        # Pre-populate cache to say "hit, entry_id=2"
        from Tooling.subsystems.dedupe import _cache_key, _write_cache
        candidate_text = candidate_lean.read_text(encoding="utf-8")
        key = _cache_key(candidate_text, two_entries, "strict")
        _write_cache(db, key, {"outcome": "hit", "entry_id": 2}, 3600.0)

        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        result = dedupe(candidate_lean, two_entries, conn=db, lake_cwd=tmp_path)
        assert result.outcome == "novel"
        assert result.from_cache is False  # mock returned, not cache

    def test_mock_does_not_write_cache(
        self, db, candidate_lean, two_entries, tmp_path, monkeypatch
    ) -> None:
        """Mock outcome must not be persisted to cache (would poison real runs)."""
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        dedupe(candidate_lean, two_entries, conn=db, lake_cwd=tmp_path)
        rows = db.execute("SELECT COUNT(*) FROM search_cache").fetchone()
        assert rows[0] == 0
