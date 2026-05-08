<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To expand `‖x - t • y‖²` in a real inner product space, chain `norm_sub_sq_real` then `inner_smul_right`, `norm_smul`, `Real.norm_eq_abs`, `sq_abs` (no bundled lemma); to "divide by `t > 0`" through `0 ≤ t * (a + t·b)`, factor with `ring`, then derive `0 ≤ a + t·b` via `by_contra` + `mul_neg_of_pos_of_neg`.
- For identities mixing scalar `•` with `+`/`-` on a normed space (e.g. `z - ((1-t) • a + t • b) = (z - a) - t • (b - a)`), use the `module` tactic; `abel` doesn't reason about `•`, and squaring a nonneg-base inequality goes via `pow_le_pow_left₀` (note the `₀`).
- Use `abel` (not `ring`) for arithmetic on `X : NormedAddCommGroup` differences; combine with `← inner_sub_left` to fold sums of inner products into a single `⟪·, ·⟫`, then close with `real_inner_self_eq_norm_sq`.
