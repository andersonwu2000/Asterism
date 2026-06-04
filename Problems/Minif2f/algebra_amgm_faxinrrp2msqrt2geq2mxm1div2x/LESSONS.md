<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `expr ≥ Real.sqrt c` goals, combine `Real.sq_sqrt (by norm_num : 0 ≤ c)` + `nlinarith [sq_nonneg (x - Real.sqrt c / 2)]` after rewriting the LHS via `field_simp; ring` to clear any positive denominator.
