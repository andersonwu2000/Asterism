<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To simplify `Real.sqrt N` when `N = n^2 * k`, use `rw [show (N : ℝ) = n^2 * k by norm_num, Real.sqrt_mul (by norm_num), Real.sqrt_sq (by norm_num)]`; after all sqrt rewrites, `field_simp` + `nlinarith [Real.mul_self_sqrt (by norm_num : (0:ℝ) ≤ k)]` closes arithmetic goals involving the remaining `√k`.
