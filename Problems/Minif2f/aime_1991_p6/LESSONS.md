<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `∑ ⌊r + k/c⌋ ≥ N` (lower bound) goals, split via `Finset.sum_union` + `Finset.sum_le_sum`, close each per-term `n ≤ ⌊r + k/c⌋` with `rw [Int.le_floor]; push_cast; have hk1 : (bound : ℝ) ≤ k := by exact_mod_cast hk.1; linarith`, and evaluate constant partial sums (e.g. `∑ _ ∈ Icc a b, n = m`) with `decide`.
- For `∑ ⌊expr_k⌋ ≤ N` goals, the canonical pattern is: split the index range via `Finset.sum_union` (prove disjointness with `omega`), then apply `Finset.sum_le_card_nsmul` to reduce to a per-term bound, close each floor bound with `Int.floor_lt.mpr` (which gives `⌊x⌋ < n ↔ x < n`) plus `omega` to convert `< n` to `≤ n-1`; `decide` handles `Finset.Icc.card` goals for concrete ℕ bounds.
- For `bound-on-r → sum-of-floors = N` sub-goals, decompose via the contrapositive (assume the negated bound, show sum is off by 1); `by_contra; rw [not_le] at hlt` then a single sub-goal `sum ≤ N-1` (or `≥ N+1`), closed against `h : sum = N` by `omega` since the floor sum lives in ℤ.
- For `⌊expr⌋ = n` goals with numeric bounds, `rw [Int.floor_eq_iff]` then `push_cast; linarith` on each branch is the canonical pattern; `push_cast` is needed to resolve the ℤ→ℝ coercion before `linarith` can close.
