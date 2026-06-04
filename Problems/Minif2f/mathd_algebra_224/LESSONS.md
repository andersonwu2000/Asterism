<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `sqrt-bound → ℕ-membership` goals, derive `n < c²` from `sqrt n < c` via `nlinarith [sq_nonneg (Real.sqrt n - c), Real.sq_sqrt (Nat.cast_nonneg n)]` — the `sq_nonneg` hint lets nlinarith square both sides without manual `sqrt_lt'` unfolding.
- For `n ∈ (Finset ℕ) → sqrt-bound` sub-goals, `fin_cases hn <;> constructor <;> norm_num [Real.sqrt_lt', Real.lt_sqrt]` closes all cases in one shot without manual sqrt squaring.
- After `rcases ... rfl` substitutes concrete ℕ values, `Real.mul_self_sqrt (by norm_num : (0:ℝ) ≤ _)` fails ("can't synthesize placeholder for x : ℝ"); fix by passing the explicit literal (e.g. `Real.mul_self_sqrt (by norm_num : (0:ℝ) ≤ 5)`) or by using `Real.sqrt_lt'` / `Real.sqrt_lt_sqrt_iff` to avoid squaring altogether.
