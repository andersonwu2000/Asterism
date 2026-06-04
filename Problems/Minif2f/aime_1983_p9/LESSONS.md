<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For `a ≤ b / c` goals with `c > 0`, use `le_div_iff₀` (subscript 0) — plain `le_div_iff` is not present in current Mathlib and will error as "Unknown identifier".
- `Real.sin_pos_of_pos_of_lt_pi : 0 < x → x < π → 0 < sin x` is the direct Mathlib lemma for sin positivity on (0, π); combine with `mul_pos` for any `x * sin x > 0` subgoal.
