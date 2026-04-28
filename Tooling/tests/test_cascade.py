"""Unit tests for Tooling.cascade dispatch table (P3 C25)."""
from __future__ import annotations

import pytest

from Tooling.cascade import DISPATCH_TABLE, CascadeAction, get_action


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

    def test_unknown_combination_returns_none(self) -> None:
        # P4 outcomes not yet in table
        assert get_action("Refuter", "proved") is None
        assert get_action("Builder", "unknown_outcome") is None

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
        }
        assert set(DISPATCH_TABLE.keys()) == expected_keys
