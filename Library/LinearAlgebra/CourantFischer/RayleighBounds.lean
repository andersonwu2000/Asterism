import Library.LinearAlgebra.CourantFischer.EigenbasisExpansion
import Mathlib

open Library.LinearAlgebra.CourantFischer.EigenbasisExpansion

/-!
# Rayleigh quotient bounds for symmetric operators

This file establishes pointwise and infimal lower and upper bounds on the Rayleigh quotient
`⟪Tx, x⟫ / ‖x‖²` of a symmetric operator `T` on a real inner product space.  The key results
are: the Rayleigh set over any submodule is bounded below (via the operator bound in finite
dimensions); for `x` in the span of the top `k + 1` eigenvectors the quotient is at least
`λ_k`; and when `x` is orthogonal to the bottom `k` eigenvectors the quotient is at most
`λ_k`.  Together these are the two spectral halves used in the Courant–Fischer minimax theorem.
-/

namespace Library.LinearAlgebra.CourantFischer.RayleighBounds

variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]

/-- The Rayleigh quotient `⟪Tx, x⟫ / ‖x‖²` is at least `-C` for any nonzero `x`, provided
the operator satisfies the pointwise norm bound `‖Tx‖ ≤ C * ‖x‖`. -/
theorem rayleigh_ge_neg_bound
    (T : E →ₗ[ℝ] E) (C : ℝ) (hC : ∀ x : E, ‖T x‖ ≤ C * ‖x‖)
    (x : E) (hx : x ≠ 0) :
    -C ≤ @inner ℝ E _ (T x) x / ‖x‖ ^ 2 := by
  have hx_norm : (0 : ℝ) < ‖x‖ := norm_pos_iff.mpr hx
  have hpos : (0 : ℝ) < ‖x‖ ^ 2 := by positivity
  have hcs : |@inner ℝ E _ (T x) x| ≤ ‖T x‖ * ‖x‖ := abs_real_inner_le_norm (T x) x
  have hC' := hC x
  have hinner_lb : -C * ‖x‖ ^ 2 ≤ @inner ℝ E _ (T x) x := by
    nlinarith [neg_abs_le (@inner ℝ E _ (T x) x), norm_nonneg x]
  exact (le_div_iff₀ hpos).mpr hinner_lb

/-- The Rayleigh quotient `⟪Tx, x⟫ / ‖x‖²` is at most `C` for any nonzero `x`, provided
the operator satisfies the pointwise norm bound `‖Tx‖ ≤ C * ‖x‖`. -/
theorem rayleigh_le_bound
    (T : E →ₗ[ℝ] E) (C : ℝ) (hC : ∀ x : E, ‖T x‖ ≤ C * ‖x‖)
    (x : E) (hx : x ≠ 0) :
    @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ C := by
  have hxnorm : 0 < ‖x‖ := norm_pos_iff.mpr hx
  have hxnorm2 : (0 : ℝ) < ‖x‖ ^ 2 := by positivity
  rw [div_le_iff₀ hxnorm2]
  calc @inner ℝ E _ (T x) x
      ≤ |@inner ℝ E _ (T x) x| := le_abs_self _
    _ ≤ ‖T x‖ * ‖x‖ := abs_real_inner_le_norm (T x) x
    _ ≤ C * ‖x‖ * ‖x‖ := by nlinarith [norm_nonneg x, hC x]
    _ = C * ‖x‖ ^ 2 := by ring

/-- The set of Rayleigh quotients `{ ⟪Tx, x⟫ / ‖x‖² | x ∈ S, x ≠ 0 }` is bounded below for
any symmetric operator `T` on a finite-dimensional space and any submodule `S`. -/
theorem rayleigh_set_bddbelow
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    (S : Submodule ℝ E) :
    BddBelow (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)  := by
  obtain ⟨C, hC⟩ : ∃ C : ℝ, ∀ x : E, ‖T x‖ ≤ C * ‖x‖ :=
    ⟨‖LinearMap.toContinuousLinearMap T‖, fun x => (LinearMap.toContinuousLinearMap T).le_opNorm x⟩
  refine ⟨-C, ?_⟩
  rintro q ⟨x, hxS, hx0, rfl⟩
  exact rayleigh_ge_neg_bound T C hC x hx0

/-- If `x` lies in the span of the eigenvectors at indices `≤ k`, then the eigenbasis
coordinate of `x` at any index `i > k` is zero. -/
theorem rayleigh_components_vanish
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}))
    (x : E) (hxS : x ∈ S) (i : Fin n) (hi : (k : ℕ) < (i : ℕ)) :
    (hT.eigenvectorBasis hn).repr x i = 0  := by
  have hx : x ∈ Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {j : Fin n | (j : ℕ) ≤ (k : ℕ)}) := hS ▸ hxS
  exact orthobasis_repr_vanish_outside_span (hT.eigenvectorBasis hn)
      (fun j => (j : ℕ) ≤ (k : ℕ)) x hx i (not_le.mpr hi)

/-- If the eigenbasis coordinates of `x` vanish for all indices `i > k`, then
`λ_k * ‖x‖² ≤ ⟪Tx, x⟫`.  The proof expands both sides in the orthonormal eigenbasis and
applies the antitone ordering of eigenvalues termwise. -/
theorem numerator_ge_eigenvalue
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hv : ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0) :
    hT.eigenvalues hn k * ‖x‖ ^ 2 ≤ @inner ℝ E _ (T x) x  := by
  have h_num : (inner ℝ (T x) x : ℝ) =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    Library.LinearAlgebra.CourantFischer.EigenbasisExpansion.rayleigh_numerator_eigenbasis hT hn x
  have h_norm : ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    Library.LinearAlgebra.CourantFischer.EigenbasisExpansion.norm_sq_eq_sum_repr_sq hT hn x
  have h_sum : hT.eigenvalues hn k * (∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2)
      ≤ ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    weighted_eigenvalue_sum_ge hT hn k x hv
  rw [h_num, h_norm]
  exact h_sum

/-- For any nonzero `x` in the span of the top `k + 1` eigenvectors of a symmetric operator,
the Rayleigh quotient satisfies `λ_k ≤ ⟪Tx, x⟫ / ‖x‖²`. -/
theorem rayleigh_ge_on_topeig
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}))
    (x : E) (hxS : x ∈ S) (hx0 : x ≠ 0) :
    hT.eigenvalues hn k ≤ @inner ℝ E _ (T x) x / ‖x‖ ^ 2  := by
  have hpos : (0:ℝ) < ‖x‖ ^ 2 := pow_pos (norm_pos_iff.mpr hx0) 2
  have hv := rayleigh_components_vanish hT hn k S hS x hxS
  have hnum := numerator_ge_eigenvalue hT hn k x hv
  exact (le_div_iff₀ hpos).mpr hnum

/-- If `x` is orthogonal to every eigenvector at index `i < k`, then the Rayleigh quotient
satisfies `⟪Tx, x⟫ / ‖x‖² ≤ λ_k`.  This is the upper-bound half of the Courant–Fischer
minimax characterisation of eigenvalues. -/
theorem rayleigh_le_of_low_modes_zero
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (x : E) (hx : x ≠ 0)
    (hzero : ∀ i : Fin n, (i : ℕ) < (k : ℕ) →
      @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0) :
    @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  have hnum : @inner ℝ E _ (T x) x
      = ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    Library.LinearAlgebra.CourantFischer.EigenbasisExpansion.rayleigh_numerator_eigenbasis hT hn x
  have hnorm : ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    norm_sq_eq_sum_repr_sq hT hn x
  have hsum_le : ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2
      ≤ hT.eigenvalues hn k * ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    weighted_eigenvalue_sum_le hT hn k x hzero
  have hpos : (0:ℝ) < ‖x‖ ^ 2 := pow_pos (norm_pos_iff.mpr hx) 2
  rw [div_le_iff₀ hpos, hnum, hnorm]
  exact hsum_le

end Library.LinearAlgebra.CourantFischer.RayleighBounds
