<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When `decide` or `push_cast; rfl` on a large ℤ-indexed `Finset.Icc` sum hits maximum recursion depth, wrap the theorem with `set_option maxRecDepth 2000 in` — this unblocks both tactics without changing the proof shape.
- `Finset.card_Icc` does not exist as a Mathlib constant (unknown constant error); for a concrete ℤ-indexed `Finset.Icc`, compute the cardinality with `decide` (e.g. `have hcard : (Finset.Icc (1:ℤ) 84).card = 84 := by decide`).
- To prove `a - b ≤ |b - a|` (pointwise, e.g. inside `Finset.sum_le_sum`), use `have h := le_abs_self (a - b)` then `rwa [abs_sub_comm] at h`; `linarith [abs_nonneg ...]` alone does not close it.
- To cast `∑ k ∈ s, (↑k : ℝ)` (ℤ-indexed sum) to `↑(∑ k ∈ s, k : ℤ)`, use `push_cast; rfl` — `simp [← Int.cast_sum]` makes no progress and `exact_mod_cast` fails; after the cast equality `heq`, `rw [heq, hsum]; norm_num` closes the ℝ value; `decide` works on `(∑ k ∈ Finset.Icc (a:ℤ) b, k : ℤ) = n` but `native_decide` fails (noncomputable ℝ instance leaks).
- To split a `Finset.Icc` sum, prove disjointness (`hd`) and union equality (`hu`) separately via `omega`, then `rw [← hu, Finset.sum_union hd]`; using `rw [← Finset.sum_union]` directly hits maximum recursion depth.
