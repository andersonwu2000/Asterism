<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To prove `⟪∑ c_i • (σ_i • b_E i), x⟫ = ∑ σ_i * ‖c_i‖²` over an RCLike field, use `simp_rw [sum_inner, smul_smul, inner_smul_left, map_mul, RCLike.conj_ofReal]` to reduce to per-element algebra, then `have hconj := RCLike.conj_mul c` and close the coercion mismatch between `(↑‖c‖)^2 : 𝕜` and `↑(‖c‖^2 : ℝ) : 𝕜` with `push_cast; ring`.
- To flip `j = i` to `i = j` inside an `if`-condition, `rw [eq_comm]` fails with "motive not type correct" (the `Decidable` instance depends on the rewritten term); use `simp only [eq_comm (a := j)]` instead, which handles the dependent instance correctly.
- To expand `(b_E.toBasis.constr 𝕜 f) x` into `∑ i, ⟪b_E i, x⟫ • f i`, use `simp [OrthonormalBasis.repr_apply_apply]`; `Basis.constr_apply_fintype` and `OrthonormalBasis.coe_toBasis_repr_apply` are both `@[simp]` so they fire automatically, but `repr_apply_apply` (giving `b.repr v i = ⟪b i, v⟫`) must be named explicitly — note `Basis.constr_apply_fintype` gives "Unknown identifier" under `rw` but works fine under `simp`.
- To prove `P.IsSymmetric` for a basis-defined operator over an orthonormal basis `b_E`, rewrite with `LinearMap.isHermitian_toMatrix_iff b_E` (the `↔` is `(P.toMatrix b_E.toBasis b_E.toBasis).IsHermitian ↔ P.IsSymmetric`, so `rw [← ...]`) to reduce abstract inner-product symmetry to a concrete finite matrix-Hermitian `ext`-check.
- `T.singularValues` is `ℕ →₀ ℝ`, so a sum `∑ i, T.singularValues i * …` infers `i : ℕ` and fails with `failed to synthesize Fintype ℕ`; when indexing over the basis write `∑ i : Fin (Module.finrank 𝕜 E), T.singularValues (i : ℕ) * …` with an explicit `Fin` binder and a `(i : ℕ)` cast.
- Map-equality goals over b_E close by `apply b_E.toBasis.ext; intro i` then `simp only [OrthonormalBasis.coe_toBasis, LinearMap.comp_apply]`; constr reduces via simp lemma `Basis.constr_basis` (fire by plain `simp`, not `rw` — Basis is in namespace `Module`), the isometry `b_E.equiv b_F` via `OrthonormalBasis.equiv_apply_basis`, and the h_col dite collapses with `dif_pos i.isLt`.
