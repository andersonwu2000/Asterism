<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For log-system goals: rewrite with `Real.log_mul hx' (pow_ne_zero n hy')` then `Real.log_pow` to linearize; follow with `push_cast` before `linarith` because `Real.log_pow` introduces a `ℕ`-cast `↑n` that `linarith` cannot clear on its own.
