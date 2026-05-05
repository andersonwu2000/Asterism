- **Existential reformulation by direct witness reuse**: Unpack the triple, set `p := a, x := b, y := c`; derive `b ≠ c` from `¬ Collinear a b b` reducing to `0 = 0` via `simp [Collinear]` or `intro rfl`.

- **Nonempty filter via explicit witness triple**: Unpack existentials, then `exact ⟨(p, a, b), membership_lemma ...⟩`; membership closed by `simp [Finset.mem_filter, Finset.mem_product]` + hypotheses. Needs `open Classical` for `Collinear` decidability.

- **Finset minimum of scaled perpendicular distance**: Filter `P ×ˢ (P ×ˢ P)` by non-collinearity, apply `Finset.exists_min_image` on the real-division objective, then cross-multiply with `s31_sub_3` using positivity of squared distances from `s31_sub_2`.

- **Sylvester–Gallai via Kelly min-distance**: Use `Finset.exists_min_image` to get a minimiser triple, then derive contradiction from a third collinear point via cross-product arithmetic; assemble with `s44_sub_1/2/3`.

- **Finset filter Nonempty via explicit witness**: `open Classical` at namespace level (not tactic-level) for `DecidablePred` on filter type; unpack existentials, derive `b ≠ c` from non-collinearity sub-lemma, close with `refine ⟨(a,b,c), ?_⟩` + `simp [mem_filter, mem_product]`.

- **Minimum cross-multiplied perpendicular distance exists**: Build a filtered product Finset of non-collinear triples, apply `Finset.exists_min_image` on the squared-distance ratio, then use `div_le_div_iff₀` to cross-multiply into the product inequality.

- **Parametric point closer to foot than off-line point**: Witness `(c, a)`; chain `d(c,a)²·L = t²L²  <  dot²+D²  = d(p,a)²·L` via Lagrange identity + `nlinarith`, then divide by `L > 0`.

- **Collinearity contradiction via line uniqueness**: Case-split `x ≠ z` into coordinate differences; transfer collinearity with `nlinarith` witnesses; then use permutation symmetry (`simp [Collinear]; ring`) to close against the negated hypothesis.

- **Closest point among collinear triple to off-line point**: Split on `t ≤ 1/2` vs `t > 1/2` via `le_or_gt`; in each branch use `(c,b)` or `(c,a)` as witness and close with `nlinarith` using squared cross-product and parametric distance identities.

- **Closest-endpoint distance on parametric segment**: `by_contra`+`not_or`; express `d(c,a)²` and `d(c,b)²` via `ring`, lift bounds with `mul_le_mul_of_nonneg_right`, apply Lagrange identity via `ring`, then close with `nlinarith`/`sq_pos_of_ne_zero` sub-lemma.
