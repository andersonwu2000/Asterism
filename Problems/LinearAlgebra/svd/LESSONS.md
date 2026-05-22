<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- To extend a partial orthonormal family to a full `OrthonormalBasis (Fin (finrank 𝕜 F)) 𝕜 F`, use `Orthonormal.exists_orthonormalBasis_extension_of_card_eq` (PiL2.lean) with `card_ι := (Fintype.card_fin _).symm`: define `v : Fin (finrank F) → F` on all indices (junk `0` outside support) and `s : Set (Fin (finrank F))` for the support, prove `Orthonormal 𝕜 (s.restrict v)`, get `b_F` with `∀ i ∈ s, b_F i = v i`; the unsuffixed `exists_orthonormalBasis_extension` returns a `Finset`-indexed basis (wrong shape).
- To prove `T.singularValues i = 0` when `finrank 𝕜 F ≤ i` (codomain bound), use `LinearMap.support_singularValues T` (gives `support = Finset.range (finrank T.range)`) + `Submodule.finrank_le T.range` + `Finsupp.mem_support_iff`; `LinearMap.singularValues_of_finrank_le` only handles the domain bound `finrank E ≤ i`.
- To compute `b_F.toBasis.repr (b_F k) = Finsupp.single k 1`, bridge via `congr_fun (OrthonormalBasis.coe_toBasis b_F) k` (which gives pointwise `b_F.toBasis k = b_F k`; `coe_toBasis` is a coercion equality, not pointwise), then close with `b_F.toBasis.repr_self k` — dot notation works where `Basis.repr_self` as a standalone name fails.
- For indicator-shaped sums `∑ j : Fin n, (if (j : ℕ) = (i : ℕ) then c else 0) • v j`, split on `h : (i : ℕ) < n` then use `Finset.sum_eq_single ⟨i.val, h⟩` with `Fin.ext` to convert the nat-equality condition into a `Fin`-equality contradiction for off-diagonal terms.
- `orthonormal_iff_ite.mp b.orthonormal i j` gives `⟨b i, b j⟩ = if i = j then 1 else 0` directly — use this whenever computing inner products of orthonormal basis vectors instead of splitting on `.1`/`.2` of the `And` manually.
- `IsSymmetric.apply_eigenvectorBasis` + `LinearMap.sq_singularValues_fin` close the eigenvalue / squared-singular-value identification directly (one `rw` each); no manual spectral reconstruction needed.
- `simp [LinearMap.comp_apply, LinearMap.adjoint_inner_left, LinearMap.adjoint_inner_right]` closes `IsSymmetric` goals for adjoint compositions in one step — no single combined Mathlib lemma is needed.
- Sub-goal slugs must match `[a-z][a-z0-9_]*` — snake_case Mathlib camelCase tokens in this problem (e.g. `is_symmetric`, `singular_values`, `eigenvector_basis`) or lake build rejects the patch.
