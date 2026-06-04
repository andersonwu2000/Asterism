<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- `Real.sqrt_sq (h : 0 ≤ x) : √(x ^ 2) = x` cleanly derives `x = √k` from `x ^ 2 = k` and `x > 0` by rewriting the hypothesis, avoiding nlinarith/sq_nonneg detours.
