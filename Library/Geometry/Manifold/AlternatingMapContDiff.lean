import Library.Geometry.Manifold.FormCoordChange       -- formCoordChange (def), formCoordChange_comp
import Library.Geometry.Manifold.FormCoordChangeCont    -- continuousOn_formCoordChange
import Library.Geometry.Manifold.FormCoordChangeSelf    -- formCoordChange_self
import Mathlib.Analysis.Analytic.CPolynomial
import Mathlib.Analysis.Analytic.Composition
import Mathlib.Analysis.Calculus.ContDiff.Basic
import Mathlib.Analysis.Calculus.ContDiff.CPolynomial
import Mathlib.Analysis.Calculus.ContDiff.Operations
import Mathlib.Analysis.Normed.Module.Alternating.Basic
import Mathlib.Analysis.Normed.Module.Multilinear.Basic
import Mathlib.Analysis.Normed.Operator.ContinuousLinearMap
import Mathlib.Topology.Algebra.Module.Alternating.Basic

set_option maxHeartbeats 800000
set_option synthInstance.maxHeartbeats 400000

/-!
# Continuous differentiability of alternating-map operations

This file establishes norm bounds for the alternatization of continuous multilinear maps
and proves that the operation of precomposing a continuous alternating map with a
continuous linear map is smooth as a function of that linear map.

## Main statements

- `alternatization_norm_le`: the operator norm of `alternatization m` is at most `(card ι)! · ‖m‖`.
- `alternatization_exists_clm`: alternatization extends to a bounded linear map on the full space.
- `contdiff_comp_continuous_linear_map_clm`: `g ↦ (· ∘L g)` is `C^n` as a map on linear maps.
-/

open Bundle
open Library.Geometry.Manifold.FormCoordChange
open Library.Geometry.Manifold.FormCoordChangeCont
open Library.Geometry.Manifold.FormCoordChangeSelf
open scoped Manifold Bundle ContDiff

namespace Library.Geometry.Manifold.AlternatingMapContDiff

/-- For any permutation `σ`, the term `sign σ • m (v ∘ σ)` has norm at most `‖m‖ * ∏ i, ‖v i‖`.
The proof splits on `sign σ = ±1`, applies `m.le_opNorm`, and reindexes the product via `σ`. -/
theorem alternatization_term_norm_le
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G)
    (σ : Equiv.Perm ι) (v : ι → E) :
    ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ ≤ ‖m‖ * ∏ i, ‖v i‖ := by
  have h1 : ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ = ‖m (v ∘ σ)‖ := by
    rcases Int.isUnit_iff.mp (Units.isUnit (Equiv.Perm.sign σ)) with h | h
    · have : Equiv.Perm.sign σ = 1 := Units.val_eq_one.mp (by exact_mod_cast h)
      simp [this]
    · have : Equiv.Perm.sign σ = -1 := Units.ext h
      simp [this, norm_neg]
  have h2 : ‖m (v ∘ σ)‖ ≤ ‖m‖ * ∏ i, ‖(v ∘ σ) i‖ := m.le_opNorm _
  have h3 : ∏ i, ‖(v ∘ σ) i‖ = ∏ i, ‖v i‖ := by
    simp only [Function.comp]
    exact Finset.prod_equiv σ (by simp) (by simp)
  linarith [h1.symm ▸ h2.trans (le_of_eq (by rw [h3]))]

/-- Pointwise norm bound for `alternatization m`: applying the alternatization to `v` has norm
at most `(card ι)! · ‖m‖ · ∏ i, ‖v i‖`, using `h_term` as the per-permutation bound. -/
theorem alternatization_pointwise_norm_le
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G)
    (h_term : ∀ (σ : Equiv.Perm ι) (v : ι → E),
      ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ ≤ ‖m‖ * ∏ i, ‖v i‖)
    (v : ι → E) :
    ‖(ContinuousMultilinearMap.alternatization m : E [⋀^ι]→L[ℝ] G) v‖
      ≤ ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖ * ∏ i, ‖v i‖ := by
  rw [ContinuousMultilinearMap.alternatization_apply_apply]
  calc ‖∑ σ : Equiv.Perm ι, Equiv.Perm.sign σ • m (v ∘ σ)‖
      ≤ ∑ σ : Equiv.Perm ι, ‖Equiv.Perm.sign σ • m (v ∘ σ)‖ := norm_sum_le _ _
    _ ≤ ∑ _σ : Equiv.Perm ι, ‖m‖ * ∏ i, ‖v i‖ :=
          Finset.sum_le_sum (fun σ _ ↦ h_term σ v)
    _ = Fintype.card (Equiv.Perm ι) * (‖m‖ * ∏ i, ‖v i‖) := by
          simp [Finset.sum_const, Finset.card_univ]
    _ = ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖ * ∏ i, ‖v i‖ := by
          rw [Fintype.card_perm]; ring

/-- `alternatization` is ℝ-linear: `alternatization (c • m) = c • alternatization m`. -/
theorem alternatization_smul
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (c : ℝ) (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G) :
    ContinuousMultilinearMap.alternatization (c • m)
      = c • ContinuousMultilinearMap.alternatization m := by
  ext v
  simp only [ContinuousMultilinearMap.alternatization_apply_apply,
    ContinuousAlternatingMap.smul_apply, ContinuousMultilinearMap.smul_apply,
    Finset.smul_sum, smul_comm c]

/-- The operator norm of `alternatization m` is at most `(card ι)! · ‖m‖`. -/
theorem alternatization_norm_le
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (m : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G) :
    ‖(ContinuousMultilinearMap.alternatization m : E [⋀^ι]→L[ℝ] G)‖
      ≤ ((Nat.factorial (Fintype.card ι)) : ℝ) * ‖m‖ := by
  refine ContinuousAlternatingMap.opNorm_le_bound _ (by positivity) fun v => ?_
  exact alternatization_pointwise_norm_le m (alternatization_term_norm_le m) v

/-- `compContinuousLinearMapCLM g` factors as `(card ι)!⁻¹ · A ∘ (· ∘ g) ∘ inclusion`,
where `A` is any continuous linear extension of alternatization. -/
theorem comp_clm_eq_inv_factorial_smul
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι]
    (A : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G →L[ℝ] (E [⋀^ι]→L[ℝ] G))
    (hA : ∀ m, A m = ContinuousMultilinearMap.alternatization m)
    (g : E →L[ℝ] F) :
    (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
      (F [⋀^ι]→L[ℝ] G) →L[ℝ] (E [⋀^ι]→L[ℝ] G)) =
    ((Fintype.card ι).factorial : ℝ)⁻¹ •
      (A.comp
        ((ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
            (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)).comp
          (ContinuousAlternatingMap.toContinuousMultilinearMapCLM ℝ))) := by
  have alt_fact : ∀ (h : E [⋀^ι]→L[ℝ] G),
      ContinuousMultilinearMap.alternatization h.toContinuousMultilinearMap =
      (Fintype.card ι).factorial • h := by
    intro h
    ext v
    simp only [ContinuousMultilinearMap.alternatization_apply_apply,
      ContinuousAlternatingMap.smul_apply,
      ContinuousAlternatingMap.coe_toContinuousMultilinearMap]
    have hperm : ∀ σ : Equiv.Perm ι, h (v ∘ ↑σ) = Equiv.Perm.sign σ • h v :=
      fun σ ↦ h.toAlternatingMap.map_perm v σ
    simp_rw [hperm]
    simp [smul_smul, Finset.sum_const, Fintype.card_perm]
  ext f
  simp only [ContinuousLinearMap.smul_apply, ContinuousLinearMap.comp_apply,
    ContinuousAlternatingMap.compContinuousLinearMapCLM_apply,
    ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear_apply_apply,
    ContinuousAlternatingMap.toContinuousMultilinearMapCLM_apply]
  rw [hA]
  have h1 : f.toContinuousMultilinearMap.compContinuousLinearMap (fun _ ↦ g) =
    (f.compContinuousLinearMap g).toContinuousMultilinearMap := rfl
  rw [h1, alt_fact, ← Nat.cast_smul_eq_nsmul ℝ, smul_smul,
    inv_mul_cancel₀ (Nat.cast_ne_zero.mpr (Nat.factorial_ne_zero _)), one_smul]

/-- The map `g ↦ compContinuousLinearMapContinuousMultilinear(· ∘ g)` is `C^n`.
The proof uses `CPolynomialAt` rather than `ContDiff.comp` to avoid instance-unification
timeouts that arise from the diagonal CLM construction. -/
theorem comp_diag_multilinear_contdiff
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] {n : ℕ∞ω} :
    ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
        (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)) := by
  refine contDiff_iff_contDiffAt.mpr fun x ↦ ?_
  have hM : CPolynomialAt ℝ
      (ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
        (fun _ : ι ↦ E) (fun _ : ι ↦ F) G) (fun _ ↦ x) :=
    ContinuousMultilinearMap.cpolynomialAt _
  have hdiag : CPolynomialAt ℝ (fun g : E →L[ℝ] F ↦ (fun _ : ι ↦ g)) x :=
    (ContinuousLinearMap.pi fun _ : ι ↦ ContinuousLinearMap.id ℝ (E →L[ℝ] F)).cpolynomialAt x
  exact (hM.fun_comp hdiag).contDiffAt

/-- Alternatization extends to a bounded linear map from continuous multilinear maps to
continuous alternating maps, with norm bound `(card ι)!`. -/
theorem alternatization_exists_clm
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι] :
    ∃ A : ContinuousMultilinearMap ℝ (fun _ : ι ↦ E) G →L[ℝ] (E [⋀^ι]→L[ℝ] G),
      ∀ m, A m = ContinuousMultilinearMap.alternatization m := by
  exact ⟨LinearMap.mkContinuous
    { toFun := ContinuousMultilinearMap.alternatization
      map_add' := fun m₁ m₂ ↦ map_add _ m₁ m₂
      map_smul' := alternatization_smul }
    ((Nat.factorial (Fintype.card ι)) : ℝ) alternatization_norm_le, fun m ↦ rfl⟩

/-- The map `g ↦ compContinuousLinearMapCLM g` sending a linear map to the operation of
precomposing alternating maps with it is `C^n` in `g`. -/
theorem contdiff_comp_continuous_linear_map_clm
    {E : Type*} [NormedAddCommGroup E] [NormedSpace ℝ E]
    {F : Type*} [NormedAddCommGroup F] [NormedSpace ℝ F]
    {G : Type*} [NormedAddCommGroup G] [NormedSpace ℝ G]
    {ι : Type*} [Fintype ι] [DecidableEq ι] {n : ℕ∞ω} :
    ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
        (F [⋀^ι]→L[ℝ] G) →L[ℝ] (E [⋀^ι]→L[ℝ] G))) := by
  obtain ⟨A, hA⟩ := alternatization_exists_clm (E := E) (G := G) (ι := ι)
  have h_diag : ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
        (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)) :=
    comp_diag_multilinear_contdiff
  have h_key : ∀ g : E →L[ℝ] F,
      (ContinuousAlternatingMap.compContinuousLinearMapCLM g :
        (F [⋀^ι]→L[ℝ] G) →L[ℝ] (E [⋀^ι]→L[ℝ] G)) =
      ((Fintype.card ι).factorial : ℝ)⁻¹ •
        (A.comp
          ((ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
              (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)).comp
            (ContinuousAlternatingMap.toContinuousMultilinearMapCLM ℝ))) :=
    fun g ↦ comp_clm_eq_inv_factorial_smul A hA g
  have h_comp : ContDiff ℝ n (fun g : E →L[ℝ] F ↦
      ((Fintype.card ι).factorial : ℝ)⁻¹ •
        (A.comp
          ((ContinuousMultilinearMap.compContinuousLinearMapContinuousMultilinear ℝ
              (fun _ : ι ↦ E) (fun _ : ι ↦ F) G (fun _ ↦ g)).comp
            (ContinuousAlternatingMap.toContinuousMultilinearMapCLM ℝ)))) :=
    (contDiff_const.clm_comp (h_diag.clm_comp contDiff_const)).const_smul _
  rw [funext h_key]
  exact h_comp

end Library.Geometry.Manifold.AlternatingMapContDiff
