# Backward Agent Prompt Template (spike-007 sizing fixture)

You are a mathematical theorem decomposition expert working with Lean 4 and Mathlib.

## Your task

Given a theorem Goal that has not been proven, decompose it into sub-goals and a proof strategy.

## Goal to decompose

**Goal ID**: G_42
**Slug**: add_comm_induction
**Kind**: theorem
**Depth**: 0
**Statement**:
```lean
theorem add_comm_induction : ∀ (n m : Nat), n + m = m + n := by sorry
```

**Source file** (Problems/sg/Goals/42_add_comm_induction/add_comm_induction.lean):
```lean
import Problems.sg.Defs

theorem add_comm_induction : ∀ (n m : Nat), n + m = m + n := by sorry
```

## Problem definitions (Problems/sg/Defs.lean)

```lean
import Mathlib

-- Sylvester-Gallai problem definitions
-- (empty for this demo - theorems use pure Mathlib)
```

## Failed attempts (dead_attempts, up to K=5)

### Attempt 1 (tactic: rfl)
- **Status**: exhausted
- **Error**: `type mismatch: n + m is not definitionally equal to m + n`
- **Tactic tried**: `by rfl`

### Attempt 2 (tactic: simp)
- **Status**: exhausted
- **Error**: `simp made no progress`
- **Tactic tried**: `by simp`

### Attempt 3 (tactic: decide)
- **Status**: exhausted
- **Error**: `cannot evaluate, the universe level is not universe-polymorphic`
- **Tactic tried**: `by decide`

### Attempt 4 (tactic: omega)
- **Status**: exhausted
- **Error**: `omega could not close the goal`
- **Tactic tried**: `by omega`

### Attempt 5 (tactic: ring)
- **Status**: exhausted
- **Error**: `ring made no progress`
- **Tactic tried**: `by ring`

## Mathlib hints (from find_lemmas stub — empty in P2)

(No Mathlib lemma hints available at this stage. Use your knowledge of Mathlib.)

## Candidate sub-goals from find_subgoals stub

(No structural sub-goals suggested. Use your knowledge of induction structure.)

## Output format

Respond with a PROPOSAL in the following JSON format:

```json
{
  "combinator": "AND",
  "strategy_description": "Prove by induction on n, with base case and inductive step",
  "sub_goals": [
    {
      "slug": "add_comm_base",
      "kind": "theorem",
      "statement": "∀ (m : Nat), 0 + m = m + 0",
      "binders": [],
      "body": "∀ (m : Nat), 0 + m = m + 0",
      "depth": 1
    },
    {
      "slug": "add_comm_step",
      "kind": "theorem",
      "statement": "∀ (n m : Nat), n + m = m + n → (n + 1) + m = m + (n + 1)",
      "binders": [],
      "body": "∀ (n m : Nat), n + m = m + n → (n + 1) + m = m + (n + 1)",
      "depth": 1
    }
  ],
  "leaf_claims": []
}
```

Rules:
1. All sub-goals must be valid Lean 4 theorem statements
2. Sub-goals must collectively prove the parent goal via the combinator
3. Sub-goal count must not exceed 8
4. Each sub-goal must carry all relevant hypotheses from the parent
5. Use Lean 4 syntax (not Lean 3)
