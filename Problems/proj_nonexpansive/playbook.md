- **Nonexpansiveness of metric projection from variational inequality**: Instantiate the variational inequality at both `(x, P y)` and `(y, P x)`, flip signs via `inner_neg_left`/`inner_neg_right`, then add and expand with `inner_sub_left`/`real_inner_self_eq_norm_sq`.

- **One-sided real inner product Cauchy-Schwarz**: Chain `le_abs_self` with `abs_real_inner_le_norm` via `linarith` or `.trans`; drop absolute value on one side of the standard CS bound.

- **Variational inequality for metric projection**: Split into per-`t` algebraic bound (convex combo + `norm_sub_sq_real`) and pure-ℝ squeeze (`sub_2`); assemble with `inner_sub_left` + `ring` + `linarith`.

- **Metric projector non-expansiveness on convex set**: Three-layer Hilbert split — variational inequality `⟨x-Px, y-Px⟩ ≤ 0`, then bilinear bound `‖Px-Py‖² ≤ ⟨x-y, Px-Py⟩`, then Cauchy–Schwarz.

- **Norm-squared ≤ inner product via metric projection**: Apply variational inequality (`⟪Px−x, z−Px⟫≥0`) twice, combine algebraically via `inner_sub_left` + `linarith`, then close with `inner_sub_left` + `real_inner_self_eq_norm_sq`.

- **Metric projector variational inequality**: Convex-combination perturbation gives per-`t` bound via `norm_sub_sq_real`+`inner_neg_left`; squeeze with `t→0⁺` real arithmetic lemma to conclude `⟨Px−x, y−Px⟩ ≥ 0`.

- **norm inequality via sq cancellation on positive norm**: Case-split on `‖·‖ = 0` vs `‖·‖ > 0`; zero branch uses `norm_nonneg`; positive branch rewrites `sq` then applies `le_of_mul_le_mul_right`. Name all implicit/instance binders explicitly with `intro`.

- **Norm bound from inner-product hypothesis**: Chain `h.trans (Cauchy-Schwarz bound)` to get `‖Px-Py‖²≤‖x-y‖·‖Px-Py‖`, then cancel via case-split on `‖Px-Py‖=0` or `le_of_mul_le_mul_right`.

- **Metric projector nonexpansiveness in Hilbert space**: Chain `‖Px−Py‖² ≤ ⟨x−y, Px−Py⟩ ≤ ‖x−y‖·‖Px−Py‖` via variational inequality + Cauchy-Schwarz, then cancel one `‖Px−Py‖` factor. Use `@inner ℝ X _` explicit form to avoid notation elaboration errors.

- **Upper-bounded-for-all-ε implies non-positive**: Split into (1) ∀ ε>0, 2a≤ε via instantiating `h` at a `t` chosen from `ε` and `b`, then (2) conclude `a≤0` by contradiction specialising at `ε=a`.
