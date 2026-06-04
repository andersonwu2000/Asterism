<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Over ℂ, `linarith` fails (not an ordered field); use `linear_combination (1:ℂ)/c * h` to scale hypotheses for factoring/root-extraction goals, then `mul_eq_zero` to split the factors.
- `rw [h_set]` under `Set.toFinset` fails with motive-not-type-correct (Fintype instance depends on the set); bridge via `have : S.toFinset = T := by ext x; simp [h_set]` then `rw` on the Finset equality.
