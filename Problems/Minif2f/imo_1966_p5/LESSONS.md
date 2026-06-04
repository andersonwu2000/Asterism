<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For pure linear-equality goals over x (e.g. `x 1 + x 2 = x 3 + x 4`), `nlinarith` succeeds directly after abs rewriting all four equations — the `(aᵢ-aⱼ)*xₖ` coefficient products do not block `nlinarith`; `linear_combination`+`mul_eq_zero` is only needed when the goal itself is nonlinear.
- For `x 3 = 0` (and symmetrically `x 2 = 0`): an alternative to direct nlinarith is to decompose into two linear intermediates `x 1 + x 2 = x 3 + x 4` (from Eq2 − Eq3, factoring `a₂ − a₃ ≠ 0` via `linear_combination` + `mul_eq_zero`) and `x 4 = x 1 + x 2 + x 3` (from Eq3 − Eq4), then close the parent with `linarith` on the two intermediates — avoids product-of-variables in hypotheses.
- For the "answer" goals `x 4 = 1/|a₁-a₄|` (use h₉) and `x 1 = 1/|a₁-a₄|` (use h₁₂): decompose by introducing `x 2 = 0` and `x 3 = 0` as sub-goals, then rewrite the single relevant equation via `abs_of_pos` (all `aᵢ-aⱼ` positive for i<j), substitute `hx2`/`hx3`, and close with `field_simp` + `linarith` — no need to combine multiple equations or use `nlinarith` on products.
- After abs rewriting, `nlinarith` fails on these subgoals because hypotheses contain products of `a`/`x` variables; instead use `linear_combination (h_eq_i - h_eq_j)` to factor out a nonzero scalar as `(a_i - a_j) * (linear_expr) = 0`, then close via `mul_eq_zero` + `linarith`.
- For imo_1966_p5 abs-equation subgoals (ordering a₁>a₂>a₃>a₄): establish positivity of all differences with `linarith`, rewrite abs terms via `abs_of_pos`/`abs_of_neg`, then close with `nlinarith` on just the relevant equation pair — only two of the four equations are needed per subgoal.
