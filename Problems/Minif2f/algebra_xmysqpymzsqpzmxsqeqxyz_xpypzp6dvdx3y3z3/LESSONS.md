<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For algebraic-identity goals conditioned on a hypothesis H, factor `(LHS - RHS)` as `poly * (H_lhs - H_rhs)` via `ring`, zero the factor with `have hzero : ... = 0 := by linarith`, then close with `linarith [mul_eq_zero_of_right poly hzero]`.
