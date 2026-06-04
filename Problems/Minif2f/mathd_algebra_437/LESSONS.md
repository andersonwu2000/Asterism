<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `y < x` from `y^3 < x^3` on ℝ, use `(Odd.strictMono_pow (by norm_num : Odd 3)).lt_iff_lt.mp`; `linarith` closes the numeric inequality step.
