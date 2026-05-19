<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- After `rw [norm_smul]` on a real scalar `t`, the goal contains `‖t‖` (not `|t|`); apply `Real.norm_eq_abs` first, then `abs_of_pos` (or `abs_of_nonneg`) to simplify to `t` — using `abs_of_pos` directly without `Real.norm_eq_abs` fails with "did not find pattern `|t|`".
- For division inequalities like `ε / (b + 1) * c < ε`, `div_lt_iff` is unavailable (unknown identifier); instead give `nlinarith` the hints `div_mul_cancel₀ ε (ne_of_gt hb) : ε / (b+1) * (b+1) = ε` and `div_pos hε hb : 0 < ε / (b+1)` to close the goal.
- For vector equalities inside `rw [...]` arguments (e.g. `P y - P x = -(P x - P y)`), use `(by abel : ...)` not `(by ring : ...)`; the space is only an `AddCommGroup`, not a `CommRing`, so `ring` fails with "`ring_nf` made no progress".
- To cancel a positive factor from `a * c ≤ b * c`, use `le_of_mul_le_mul_right h hpos`; `mul_le_mul_right` in Mathlib4 is NOT an iff and will type-error.
