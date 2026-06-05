import Library.LinearAlgebra.CourantFischer.EigenbasisExpansion
import Library.LinearAlgebra.CourantFischer.RayleighBounds
import Library.LinearAlgebra.CourantFischer.SubmoduleLemmas
import Mathlib

open Library.LinearAlgebra.CourantFischer.EigenbasisExpansion
open Library.LinearAlgebra.CourantFischer.RayleighBounds
open Library.LinearAlgebra.CourantFischer.SubmoduleLemmas

namespace Library.LinearAlgebra.CourantFischer.TestSubspaces

-- Construct W as the span of the bottom eigenvectors {bᵢ : k ≤ i}, abstracting
-- the eigenvector basis to a generic orthonormal basis `b`.
-- finrank_span_image_high: |{i : k ≤ i}| = n−k gives the dimension count.
-- inner_eq_zero_of_mem_span_high: orthonormality kills ⟪bᵢ, x⟫ for i<k (x ∈ bottom modes).

theorem bottom_eigenspace_with_support
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ W : Submodule ℝ E, Module.finrank ℝ W = n - (k : ℕ) ∧
      ∀ x : E, x ∈ W → ∀ i : Fin n, (i : ℕ) < (k : ℕ) →
        @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0  := by
  set b := hT.eigenvectorBasis hn with hb
  refine ⟨Submodule.span ℝ (b '' {i : Fin n | (k : ℕ) ≤ (i : ℕ)}), ?_, ?_⟩
  · exact finrank_span_image_high b (k : ℕ)
  · exact inner_eq_zero_of_mem_span_high b (k : ℕ)

-- Construct the bottom (n−k)-eigenvector subspace W and bound its Rayleigh quotient.
-- bottom_eigenspace_with_support: ∃ W, finrank W = n−k whose vectors have all
--   "high" eigen-modes < k vanishing (⟪eᵢ, x⟫ = 0 for i < k) — the construction half.
-- rayleigh_le_of_low_modes_zero: any x with those modes zero has Rayleigh ≤ λ_k via
--   the eigenbasis expansion + eigenvalue antitonicity — the spectral half, W-free.
-- Combine: pull W from the first, feed its support property into the second pointwise.
theorem bottom_eigenspace_exists
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ W : Submodule ℝ E, Module.finrank ℝ W = n - (k : ℕ) ∧
      ∀ x : E, x ∈ W → x ≠ 0 →
        @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  obtain ⟨W, hWrank, hWsupp⟩ := bottom_eigenspace_with_support hT hn k
  exact ⟨W, hWrank, fun x hxW hx0 =>
    rayleigh_le_of_low_modes_zero hT hn k x hx0 (hWsupp x hxW)⟩

-- Direct leaf: the Rayleigh set is nonempty because e_k = eigenvectorBasis k
-- is a nonzero element of S (k ≤ k puts it in the spanning image set), so its
-- Rayleigh quotient is a member. No sub-goals needed.
theorem topeig_set_nonempty
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)})) :
    (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2).Nonempty  := by
  refine ⟨_, (hT.eigenvectorBasis hn) k, ?_, ?_, rfl⟩
  · rw [hS]
    apply Submodule.subset_span
    exact ⟨k, by simp, rfl⟩
  · exact (hT.eigenvectorBasis hn).toBasis.ne_zero k

-- S = span of the top (k+1) eigenvectors; finrank = #generators since they are independent.
-- hA: the eigenvectorBasis vectors over the index set {i ≤ k} are linearly independent
--     (so the span's dimension equals the number of generators);
-- hB: that index set has exactly k+1 elements.
-- Combine: rewrite the image as a range, apply finrank_span_eq_card hA, close with hB.
theorem topeig_subspace_finrank
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)})) :
    Module.finrank ℝ S = (k : ℕ) + 1  := by
  have hA : LinearIndependent ℝ
      (fun i : ↥{i : Fin n | (i : ℕ) ≤ (k : ℕ)} => (hT.eigenvectorBasis hn) (i : Fin n)) :=
    topeig_eigenbasis_linindep_on_set hT hn k
  have hB : Fintype.card {i : Fin n // (i : ℕ) ≤ (k : ℕ)} = (k : ℕ) + 1 :=
    topeig_le_subtype_card k
  rw [hS, Set.image_eq_range, finrank_span_eq_card hA]
  exact hB

-- Witness subspace S = span of the top (k+1) eigenvectors {e_0,…,e_k}.
-- Three sub-goals: (1) finrank S = k+1; (2) the Rayleigh set is nonempty;
-- (3) every nonzero x ∈ S has Rayleigh ≥ λ_k (heart: λ_i ≥ λ_k for i ≤ k by
-- antitone, expand numerator in the eigenbasis).  Then le_csInf glues (2)+(3)
-- into λ_k ≤ sInf, and S, (1) discharge the existential.
theorem exists_test_subspace_inf_ge_eigenvalue
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∃ S : Submodule ℝ E,
      Module.finrank ℝ S = (k : ℕ) + 1 ∧
      hT.eigenvalues hn k ≤ sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
        q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)  := by
  refine ⟨Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}), ?_, ?_⟩
  · exact topeig_subspace_finrank hT hn k _ rfl
  · apply le_csInf
    · exact topeig_set_nonempty hT hn k _ rfl
    · rintro q ⟨x, hxS, hx0, rfl⟩
      exact rayleigh_ge_on_topeig hT hn k _ rfl x hxS hx0

-- BddAbove of the outer Courant–Fischer set {sInf(Rayleigh S) : finrank S = k+1}.
-- Upper bound = C, where ‖T x‖ ≤ C‖x‖ (operator bound, cited inline via toContinuousLinearMap).
-- For each S: exists_nonzero_mem_of_finrank_pos gives a nonzero x ∈ S (finrank = k+1 > 0);
-- rayleigh_le_bound bounds its Rayleigh quotient ≤ C; rayleigh_bddbelow_for_subspace gives
-- BddBelow, so csInf_le_of_le pushes sInf(Rayleigh S) ≤ (that quotient) ≤ C.
theorem rayleigh_sup_set_bdd_above
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    BddAbove (setOf fun r : ℝ => ∃ S : Submodule ℝ E,
      Module.finrank ℝ S = (k : ℕ) + 1 ∧
      r = sInf (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
        q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2))  := by
  obtain ⟨C, hC⟩ : ∃ C : ℝ, ∀ x : E, ‖T x‖ ≤ C * ‖x‖ :=
    ⟨‖LinearMap.toContinuousLinearMap T‖, fun x => (LinearMap.toContinuousLinearMap T).le_opNorm x⟩
  refine ⟨C, ?_⟩
  rintro r ⟨S, hScard, rfl⟩
  obtain ⟨x, hxS, hx0⟩ := exists_nonzero_mem_of_finrank_pos S (k : ℕ) hScard
  exact csInf_le_of_le (rayleigh_bddbelow_for_subspace hT S)
    ⟨x, hxS, hx0, rfl⟩ (rayleigh_le_bound T C hC x hx0)

end Library.LinearAlgebra.CourantFischer.TestSubspaces
