<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `Equiv ℝ ℝ` goals where the statement uses `σ.1` / `σ.2` (= `toFun` / `invFun`), chain `σ.right_inv y : σ.1 (σ.2 y) = y` after rewriting with the given `σ.2 a = b` hypotheses — avoids reaching for `Equiv.symm_apply_apply` or `apply_symm_apply`.
