<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- When setting up `Real.rpow_natCast` to convert `x^(3:ℝ)` → `x^(3:ℕ)`, the intermediate `show` rewrite must produce the coercion form `↑(3 : ℕ)` (not a bare `(3 : ℝ)` literal) or `Real.rpow_natCast` cannot pattern-match `?x ^ ↑?n` and the rewrite silently fails.
- To prove `(x²)^(3/2) = x^3` for `x ≥ 0`, use `Real.rpow_natCast` to lift monoid `^2`/`^3` to `Real.rpow`, then `Real.rpow_mul` to collapse `2*(3/2)=3`; `nlinarith` with `Real.sq_sqrt` closes the `52±6√43=(3±√43)²` rewrite.
