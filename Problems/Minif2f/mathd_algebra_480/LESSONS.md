<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- The `π` in the theorem statement auto-binds as a free `ℝ` variable (Defs.lean's `open Real` doesn't propagate into patch.lean); prefix the theorem with `open Real in` so `π` resolves to `Real.pi`, then `Real.pi_nonneg` + `Real.pi_lt_four` close `0 ≤ π ∧ π < 4`.
