<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- For goals of shape `(u−c)×(v−c) · D = A · (proj_u − proj_v)` where u,v lie on line ab, close with `unfold Collinear at hu hv; linear_combination -pv*hu + pu*hv` where `pu=(u.1-c.1)*(b.1-a.1)+(u.2-c.2)*(b.2-a.2)` and pv likewise; the sign is easy to reverse (pv·hu−pu·hv fails, −pv·hu+pu·hv succeeds).
- To "square" an equality `h : X = Y` inside a big polynomial `linear_combination` (e.g. deriving `X²·D² = A²·(pu-pv)²` from `X·D = A·(pu-pv)`), feed it as `(X + Y) * h` — encoding `X² − Y² = (X+Y)(X−Y)`; `rw [h]` on Kelly-sized expressions (plus `set` abbreviations) triggers `(deterministic) whnf-timeout` at 200000 heartbeats.
- `patch.lean` must include `import Problems.sylvester_gallai.Defs` explicitly — the LSP `validate_file` tool auto-prepends it (masking the gap), but `lake env lean patch.lean` does not, so any use of `Collinear` without that import fails with "Application type mismatch" universe-sort errors.
- For `(b.1-a.1)^2 + (b.2-a.2)^2 > 0` goals, combine `positivity` (nonneg half) + contradiction via `nlinarith [sq_nonneg (b.1-a.1), sq_nonneg (b.2-a.2)]` to extract component equalities from `sum = 0`, then close with `lt_of_le_of_ne hnn (Ne.symm hne)`; direct `nlinarith` on the `> 0` goal without this split fails.
- For ratio inequalities `a/b < c/d` (perpendicular-distance² comparisons in Kelly), `div_lt_div_iff` does not exist; use `rw [div_lt_div_iff₀ hb_pos hd_pos]` to reduce to the cross-multiplied polynomial form `a*d < c*b`.
- To transfer non-collinearity across line representations, use `linear_combination (v.i-c.i)*hcoll_u + (c.i-u.i)*hcoll_v - (b.i-a.i)*hcoll_cvu` (for i=1 and i=2) to prove `det_abc*(v.i-u.i)=0`, then extract `det_abc=0` via `mul_eq_zero.mp` + `u≠v` unpacked with `Prod.ext_iff`/`not_and_or`.
- `le_or_lt` does not exist in this Lean 4 Mathlib; use `le_or_gt 0 x` (gives `0 ≤ x ∨ 0 > x`) or `lt_or_ge` for sign case-splits on real numbers.
- The custom `Collinear` def is opaque to `show` (not reducible) — use `unfold Collinear; ring` to discharge degenerate cases like `Collinear a b a` / `Collinear a b b` or to rewrite to the determinant form.
- For finite-extremal goals over triples, `classical; Finset.exists_min_image` on `(Q ×ˢ Q ×ˢ Q).filter (¬ Collinear ·)` works directly — `classical` is needed since the custom `Collinear` predicate has no `DecidablePred` instance.
