import Mathlib

namespace Library.LinearAlgebra.SVD.SingularValues

-- singular_values_zero_high: support_singularValues + Submodule.finrank_le show
-- T.singularValues i = 0 for i ≥ finrank F (support ⊆ Finset.range (finrank T.range))
theorem singular_values_zero_high : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (i : ℕ), Module.finrank 𝕜 F ≤ i → T.singularValues i = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T i hi
  have hsupp : T.singularValues.support = Finset.range (Module.finrank 𝕜 T.range) :=
    LinearMap.support_singularValues T
  have hrange : Module.finrank 𝕜 T.range ≤ Module.finrank 𝕜 F :=
    Submodule.finrank_le T.range
  have hni : i ∉ T.singularValues.support := by
    rw [hsupp]
    simp only [Finset.mem_range, not_lt]
    exact le_trans hrange hi
  simp only [Finsupp.mem_support_iff, ne_eq, not_not] at hni
  exact hni

-- entry_kind: Builder
-- t_apply_zero_of_singular_zero: if σ_i = 0 then T(b_E i) = 0, via ‖T(b_E i)‖² = σ_i² = 0
theorem t_apply_zero_of_singular_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (i : Fin (Module.finrank 𝕜 E)),
  T.singularValues (i : ℕ) = 0 → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner i h_zero
  have hii := h_inner i i
  simp only [↓reduceIte] at hii
  rw [h_zero] at hii
  simp only [ne_eq, OfNat.ofNat_ne_zero, not_false_eq_true, zero_pow, RCLike.ofReal_zero] at hii
  exact inner_self_eq_zero.mp hii

-- entry_kind: Builder
-- t_b_e_zero_of_sigma_zero: σ_i = 0 → T(b_E i) = 0, via ⟨T v, T v⟩ = σ²=0 and inner_self_eq_zero
set_option linter.unusedVariables false in
theorem t_b_e_zero_of_sigma_zero : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0)
  (h_zero : ∀ (i : Fin (Module.finrank 𝕜 E)),
    ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0),
  ∀ (i : Fin (Module.finrank 𝕜 E)),
    (T.singularValues i : ℝ) = 0 → T (b_E i) = 0 := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner _h_zero i hi
  apply (inner_self_eq_zero (𝕜 := 𝕜)).mp
  have h := h_inner i i
  simp only [] at h
  rw [h, hi]
  norm_num

-- Split into (A) `singular_values_zero_high`: a pure singular-value fact —
-- T.singularValues i = 0 once i ≥ finrank F (rank ≤ codim + antitone),
-- independent of b_E / h_inner; and (B) `t_apply_zero_of_singular_zero`:
-- given that σ_i = 0 and the diagonal inner-product identity from h_inner,
-- conclude T (b_E i) = 0 via ‖T (b_E i)‖² = σ_i² = 0.
theorem t_apply_eigenbasis_zero_high : ∀ {𝕜 : Type*} [RCLike 𝕜]
  {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
  [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
  (T : E →ₗ[𝕜] F)
  (b_E : OrthonormalBasis (Fin (Module.finrank 𝕜 E)) 𝕜 E)
  (h_inner : ∀ i j, @inner 𝕜 _ _ (T (b_E i)) (T (b_E j)) =
    if i = j then (((T.singularValues i : ℝ)^2 : 𝕜)) else 0),
  ∀ (i : Fin (Module.finrank 𝕜 E)),
  ¬((i : ℕ) < Module.finrank 𝕜 F) → T (b_E i) = 0  := by
  intro 𝕜 _ E F _ _ _ _ _ _ T b_E h_inner i hi
  have hge : Module.finrank 𝕜 F ≤ (i : ℕ) := not_lt.mp hi
  have h_sigma_zero : T.singularValues (i : ℕ) = 0 :=
    singular_values_zero_high T (i : ℕ) hge
  exact t_apply_zero_of_singular_zero T b_E h_inner i h_sigma_zero

end Library.LinearAlgebra.SVD.SingularValues
