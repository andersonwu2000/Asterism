<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The `2 ^ y` term has `y : ℝ` so it elaborates as `Real.rpow`, not `HPow ℕ`; reduce via `rw [show (2:ℝ) = ((2:ℕ):ℝ) by norm_num, Real.rpow_natCast]` before `norm_num`.
