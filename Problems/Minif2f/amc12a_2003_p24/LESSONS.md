<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For goals with `Real.logb x (a / b)`, unfold via `simp only [Real.logb, Real.log_div ha.ne' hb.ne']` (note: `Real.log_div` takes nonzero args, use `.ne'` on positivity hypotheses), then `field_simp [hloga_ne, hlogb_ne]` + `ring` closes algebraic log identities cleanly.
- For goals `-(...)^2 / (log a * log b) ≤ 0` with `1 < b ≤ a`, use `apply div_nonpos_of_nonpos_of_nonneg` then `linarith [sq_nonneg ...]` for the numerator and `linarith` after `mul_pos (Real.log_pos ...) (Real.log_pos ...)` for the denominator; get `1 < a` via `lt_of_lt_of_le hb hab`.
