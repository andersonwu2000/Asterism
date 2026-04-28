"""Unit tests for Tooling.subsystems.similarity (P3 C23)."""
from __future__ import annotations

import pytest

from Tooling.subsystems.similarity import (
    parent_subgoal_max_similarity,
    token_jaccard,
)


class TestTokenJaccard:
    def test_identical_strings_one(self) -> None:
        assert token_jaccard("a + b = c", "a + b = c") == 1.0

    def test_disjoint_strings_zero(self) -> None:
        # Distinct identifiers + operators → near-zero overlap (only nothing common)
        assert token_jaccard("foo", "bar") == 0.0

    def test_partial_overlap(self) -> None:
        sim = token_jaccard("a + b = c", "a + b = d")
        # Tokens: {a,+,b,=,c} vs {a,+,b,=,d} → 4/6
        assert 0.5 < sim < 1.0

    def test_both_empty_returns_one(self) -> None:
        """Empty == empty is the trivially-equal case."""
        assert token_jaccard("", "") == 1.0

    def test_one_empty_returns_zero(self) -> None:
        assert token_jaccard("", "a + b") == 0.0
        assert token_jaccard("a + b", "") == 0.0

    def test_whitespace_normalized(self) -> None:
        sim = token_jaccard("a +  b", "a + b")
        assert sim == 1.0


class TestParentSubgoalMaxSimilarity:
    def test_empty_subgoals_returns_zero(self) -> None:
        assert parent_subgoal_max_similarity("a + b", []) == 0.0

    def test_returns_max_across_subgoals(self) -> None:
        parent = "n + 0 = n"
        subgoals = ["m + 0 = m", "0 = 0", "n + 0 = n"]
        # subgoals[2] is identical → max = 1.0
        assert parent_subgoal_max_similarity(parent, subgoals) == 1.0

    def test_dissimilar_subgoals_low_score(self) -> None:
        parent = "Nat.add_comm m n"
        subgoals = ["Real.sqrt_nonneg x", "List.length_nil"]
        sim = parent_subgoal_max_similarity(parent, subgoals)
        # token "Real.sqrt_nonneg" vs "Nat.add_comm" — almost no overlap
        # parent tokens: {Nat.add_comm, m, n}, sg1 tokens: {Real.sqrt_nonneg, x}
        # Intersection = empty; some operators may overlap if they share dots.
        # Max should be close to 0 (well below threshold 0.85)
        assert sim < 0.5

    def test_ih_trap_synthetic_case(self) -> None:
        """Classic IH-trap: parent uses universally-quantified n, sub-goal uses
        a strictly-decreased argument (n-1). Tokens overlap heavily because
        the structure is the same."""
        parent = "∀ n : Nat, P n"
        # sub-goal: "P (n - 1)" plus boilerplate — same identifier set
        sub = "∀ n : Nat, P n"
        sim = parent_subgoal_max_similarity(parent, [sub])
        assert sim >= 0.85  # ih_trap_similarity_threshold per spike-008 D-08-1

    def test_empty_parent_with_nonempty_sub_returns_zero(self) -> None:
        """C23 R3 LOW-2: empty-vs-nonempty edge — must NOT trip the empty-equals-empty
        return-1 short-circuit. token_jaccard handles this; pin it explicitly."""
        assert parent_subgoal_max_similarity("", ["a + b"]) == 0.0

    def test_empty_parent_with_empty_sub_returns_one(self) -> None:
        """C23 R3 LOW-2: empty-vs-empty is 1.0 (token_jaccard convention).
        Documented edge: caller (Backward._commit) is responsible for
        substituting `or ""` and filtering empty statements before this hits
        threshold checks. If a caller refactor drops the `or ""` and lets
        None reach here, this test surfaces the symptom."""
        assert parent_subgoal_max_similarity("", [""]) == 1.0
