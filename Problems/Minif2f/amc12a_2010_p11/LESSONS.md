<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To recover `b` from `x = Real.logb b K` (with `0 < b`, `0 < K`, `K ≠ 1`), derive `b ≠ 1` (else `Real.logb 1 K = 0` forces `x = 0`), then use `Real.rpow_logb h₀ hb_ne_1 hK_pos` to rewrite `b ^ x = K`; combined with a sibling `c ^ x = K`, take `Real.log`, apply `Real.log_rpow`, cancel `x` via `mul_left_cancel₀`, and close with `Real.log_injOn_pos`.
- When `Real.rpow_add` splits an exponent and the goal's RHS uses nat-pow (e.g. `7^7 : ℝ`), use `Real.rpow_natCast` to align the rpow form with the nat-pow form before closing with `field_simp` + `ring`.
