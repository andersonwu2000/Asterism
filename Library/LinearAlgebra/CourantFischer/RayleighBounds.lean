import Library.LinearAlgebra.CourantFischer.EigenbasisExpansion
import Mathlib

open Library.LinearAlgebra.CourantFischer.EigenbasisExpansion

namespace Library.LinearAlgebra.CourantFischer.RayleighBounds

-- rayleigh_ge_neg_bound: Rayleigh quotient ≥ -C via Cauchy-Schwarz + operator bound.
-- Cauchy-Schwarz gives ⟪Tx,x⟫ ≥ -‖Tx‖·‖x‖; the operator bound hC gives ‖Tx‖ ≤ C·‖x‖;
-- combining yields ⟪Tx,x⟫ ≥ -C·‖x‖², and dividing by ‖x‖² > 0 closes the goal.
theorem rayleigh_ge_neg_bound
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
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

-- rayleigh_le_bound: Rayleigh quotient ⟪Tx,x⟫/‖x‖² ≤ C given operator bound ‖Tx‖ ≤ C‖x‖
-- Chain: inner ≤ |inner| ≤ ‖Tx‖·‖x‖ ≤ C·‖x‖², then divide by ‖x‖² > 0.
theorem rayleigh_le_bound
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
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

-- BddBelow of the Rayleigh set: exhibit -C as a lower bound, where C bounds the
-- operator norm of T (finite-dim ⇒ T is bounded, cited inline via toContinuousLinearMap).
-- Sole sub-goal `rayleigh_ge_neg_bound` drops the set/sInf layer: for any nonzero x,
-- Cauchy–Schwarz + the operator bound give ⟪Tx,x⟫/‖x‖² ≥ -C.
theorem rayleigh_set_bddbelow
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    (S : Submodule ℝ E) :
    BddBelow (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2)  := by
  obtain ⟨C, hC⟩ : ∃ C : ℝ, ∀ x : E, ‖T x‖ ≤ C * ‖x‖ :=
    ⟨‖LinearMap.toContinuousLinearMap T‖, fun x => (LinearMap.toContinuousLinearMap T).le_opNorm x⟩
  refine ⟨-C, ?_⟩
  rintro q ⟨x, hxS, hx0, rfl⟩
  exact rayleigh_ge_neg_bound T C hC x hx0

theorem rayleigh_bddbelow_for_subspace
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    (S : Submodule ℝ E) :
    BddBelow (setOf fun q : ℝ => ∃ x : E, x ∈ S ∧ x ≠ 0 ∧
      q = @inner ℝ E _ (T x) x / ‖x‖ ^ 2) := by apply rayleigh_set_bddbelow <;> assumption

-- For x in the span of an orthonormal sub-family, the repr-components at
-- indices outside that family vanish — pure orthonormality, independent of T.
-- Reduce the concrete top-(k+1) eigenvector span to the abstract lemma:
-- predicate P j := (j:ℕ) ≤ k, and ¬P i follows from k < i.
theorem rayleigh_components_vanish
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n)
    (S : Submodule ℝ E)
    (hS : S = Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {i : Fin n | (i : ℕ) ≤ (k : ℕ)}))
    (x : E) (hxS : x ∈ S) :
    ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0  := by
  intro i hi
  have hx : x ∈ Submodule.span ℝ ((hT.eigenvectorBasis hn) ''
      {j : Fin n | (j : ℕ) ≤ (k : ℕ)}) := hS ▸ hxS
  exact orthobasis_repr_vanish_outside_span (hT.eigenvectorBasis hn)
      (fun j => (j : ℕ) ≤ (k : ℕ)) x hx i (not_le.mpr hi)

-- Rayleigh numerator bound: expand both sides in the orthonormal eigenbasis.
-- (1) ⟪Tx,x⟫ = ∑ λᵢ·(repr x i)²  (numerator_eigenbasis_expand);
-- (2) ‖x‖² = ∑ (repr x i)²        (norm_sq_eq_sum_repr_sq_2);
-- (3) with the high modes (i>k) vanishing, antitone spectrum gives the
--     termwise/summed bound λ_k·∑(repr)² ≤ ∑ λᵢ·(repr)² (weighted_eigenvalue_sum_ge).
-- Rewrite by (1),(2) and close with (3).
theorem numerator_ge_eigenvalue
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) (x : E)
    (hv : ∀ i : Fin n, (k : ℕ) < (i : ℕ) →
      (hT.eigenvectorBasis hn).repr x i = 0) :
    hT.eigenvalues hn k * ‖x‖ ^ 2 ≤ @inner ℝ E _ (T x) x  := by
  have h_num : (inner ℝ (T x) x : ℝ) =
      ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    numerator_eigenbasis_expand hT hn x
  have h_norm : ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    norm_sq_eq_sum_repr_sq_2 hT hn x
  have h_sum : hT.eigenvalues hn k * (∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2)
      ≤ ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    weighted_eigenvalue_sum_ge hT hn k x hv
  rw [h_num, h_norm]
  exact h_sum

-- For x in the top-(k+1) eigenvector span S, the Rayleigh quotient ≥ λ_k.
-- Decouple into: (1) components of x outside the top (k+1) eigendirections
-- vanish (pure geometry of S); (2) with those vanishing, the eigenbasis
-- expansion gives the numerator bound λ_k·‖x‖² ≤ ⟪Tx,x⟫ (antitone spectrum).
-- Divide by ‖x‖² > 0 (x ≠ 0) to close.
theorem rayleigh_ge_on_topeig
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
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

-- Spectral half (W-free): expand Rayleigh in the eigenbasis and bound by λ_k.
-- hnum: ⟪Tx,x⟫ = ∑ᵢ λᵢ·(repr x i)²  (own sub-goal; dedupes to sibling).
-- hnorm: ‖x‖² = ∑ᵢ (repr x i)²  (Parseval, leaf).
-- hsum_le: ∑ᵢ λᵢ·(repr x i)² ≤ λ_k·∑ᵢ (repr x i)²  (low modes vanish + antitone).
-- Combine by clearing the positive denominator ‖x‖²>0.
theorem rayleigh_le_of_low_modes_zero
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    [FiniteDimensional ℝ E] {T : E →ₗ[ℝ] E} (hT : T.IsSymmetric)
    {n : ℕ} (hn : Module.finrank ℝ E = n) (k : Fin n) :
    ∀ x : E, x ≠ 0 →
      (∀ i : Fin n, (i : ℕ) < (k : ℕ) →
        @inner ℝ E _ ((hT.eigenvectorBasis hn) i) x = 0) →
      @inner ℝ E _ (T x) x / ‖x‖ ^ 2 ≤ hT.eigenvalues hn k  := by
  intro x hx hzero
  have hnum : @inner ℝ E _ (T x) x
      = ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    rayleigh_numerator_in_eigenbasis hT hn x
  have hnorm : ‖x‖ ^ 2 = ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    norm_sq_eq_sum_repr_sq hT hn x
  have hsum_le : ∑ i, hT.eigenvalues hn i * (hT.eigenvectorBasis hn).repr x i ^ 2
      ≤ hT.eigenvalues hn k * ∑ i, (hT.eigenvectorBasis hn).repr x i ^ 2 :=
    weighted_eigenvalue_sum_le hT hn k x hzero
  have hpos : (0:ℝ) < ‖x‖ ^ 2 := pow_pos (norm_pos_iff.mpr hx) 2
  rw [div_le_iff₀ hpos, hnum, hnorm]
  exact hsum_le

end Library.LinearAlgebra.CourantFischer.RayleighBounds
