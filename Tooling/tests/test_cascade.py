"""Unit tests for Tooling.cascade dispatch table (P3 C25; P4 C30 extended)."""
from __future__ import annotations

import pytest

from Tooling.cascade import (
    DISPATCH_TABLE,
    CascadeAction,
    CascadeFault,
    check_cascade_fault,
    get_action,
)


class TestDispatchTable:
    def test_builder_proved_action_present(self) -> None:
        action = get_action("Builder", "proved")
        assert action is not None
        assert action.name == "builder_proved"
        assert "update_goal_proved" in action.side_effects

    def test_builder_exhausted_marks_dead(self) -> None:
        action = get_action("Builder", "exhausted")
        assert action is not None
        assert action.name == "builder_dead"
        assert "update_strategy_dead" in action.side_effects

    def test_builder_hassorry_same_as_exhausted(self) -> None:
        a1 = get_action("Builder", "exhausted")
        a2 = get_action("Builder", "hasSorry")
        assert a1 is not None and a2 is not None
        assert a1.name == a2.name == "builder_dead"

    def test_backward_success_action(self) -> None:
        action = get_action("Backward", "success")
        assert action is not None
        assert action.name == "backward_success"

    def test_backward_failure_outcomes_share_action_name(self) -> None:
        a1 = get_action("Backward", "exhausted")
        a2 = get_action("Backward", "unproductive")
        assert a1 is not None and a2 is not None
        assert a1.name == a2.name == "backward_failure"
        assert "archive_check_backward" in a1.side_effects

    def test_refuter_success_action_present(self) -> None:
        """P4 C30: Refuter success acknowledges ¬G insertion (no direct cascade)."""
        action = get_action("Refuter", "success")
        assert action is not None
        assert action.name == "refuter_success"
        assert "acknowledge_negation_goal" in action.side_effects

    def test_refuter_exhausted_records_failure(self) -> None:
        """P4 C30: Refuter exhausted mirrors Backward exhausted (dead_attempts + archive)."""
        action = get_action("Refuter", "exhausted")
        assert action is not None
        assert action.name == "refuter_failure"
        assert "record_refuter_failure" in action.side_effects
        assert "archive_check_refuter" in action.side_effects

    def test_unknown_combination_returns_none(self) -> None:
        # Counterexample / Forward / Generalizer / ConstructionSearch / Strategist
        # outcomes are still not in the table (P5+ pipelines).
        assert get_action("Counterexample", "silver") is None
        assert get_action("Builder", "unknown_outcome") is None
        # Refuter unknown outcome (only success / exhausted are dispatched).
        assert get_action("Refuter", "proved") is None

    def test_action_dataclass_frozen(self) -> None:
        action = get_action("Builder", "proved")
        with pytest.raises(Exception):
            action.name = "mutated"  # type: ignore[misc]

    def test_table_has_no_duplicate_keys(self) -> None:
        """sanity: dict keys are unique by definition; verify expected coverage."""
        expected_keys = {
            ("Builder", "proved"),
            ("Builder", "exhausted"),
            ("Builder", "hasSorry"),
            ("Backward", "success"),
            ("Backward", "exhausted"),
            ("Backward", "unproductive"),
            # P4 C30:
            ("Refuter", "success"),
            ("Refuter", "exhausted"),
            # P7 C52-C54:
            ("Forward", "success"),
            ("Forward", "no_novel"),
            ("Forward", "exhausted"),
            ("Generalizer", "success"),
            ("Generalizer", "no_novel"),
            ("Generalizer", "unproductive"),
            ("Generalizer", "exhausted"),
            ("Strategist", "success"),
            ("Strategist", "exhausted"),
            # P7 演習 refactor (路線 1):
            ("Solver", "success"),
            ("Solver", "exhausted"),
        }
        assert set(DISPATCH_TABLE.keys()) == expected_keys

    def test_target_ids_default_empty_tuple(self) -> None:
        """C25 R3 HIGH-4: forward-compat field for P4 twin propagation
        defaults to empty tuple; P3+P4 actions are all single-target.
        Multi-target (twin propagation) handled by scheduler twin cascade
        helper, not via this field — field reserved for P5/P6 expansion."""
        for action in DISPATCH_TABLE.values():
            assert action.target_ids == ()


class TestCascadeFault:
    """P4 C30: CASCADE_FAULT env hook for acceptance #9 fatal-halt path."""

    def test_no_env_no_raise(self, monkeypatch) -> None:
        monkeypatch.delenv("CASCADE_FAULT", raising=False)
        # Should not raise for any mode
        check_cascade_fault("dual_proved")
        check_cascade_fault("unique_violation")
        check_cascade_fault("fk_invalid")

    def test_dual_proved_match_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("CASCADE_FAULT", "dual_proved")
        with pytest.raises(CascadeFault, match="dual_proved"):
            check_cascade_fault("dual_proved")

    def test_mode_mismatch_no_raise(self, monkeypatch) -> None:
        monkeypatch.setenv("CASCADE_FAULT", "dual_proved")
        # Different mode → no raise
        check_cascade_fault("unique_violation")
        check_cascade_fault("fk_invalid")

    def test_unique_violation_mode_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("CASCADE_FAULT", "unique_violation")
        with pytest.raises(CascadeFault, match="unique_violation"):
            check_cascade_fault("unique_violation")

    def test_fk_invalid_mode_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("CASCADE_FAULT", "fk_invalid")
        with pytest.raises(CascadeFault, match="fk_invalid"):
            check_cascade_fault("fk_invalid")
