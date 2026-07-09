import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup

/-!
# Homology of the zero-dimensional sphere

This file computes the singular homology of `S⁰`, the unit sphere in
`EuclideanSpace ℝ (Fin 1)`, i.e. the two-point space `{±e₀}`.

## Main definitions

* `sphere_zero_index_equiv`: `S⁰` is equivalent to `Fin 2`.
* `sphere_zero_coprod_prod_iso`: the coproduct of `R`-modules indexed by `S⁰` is isomorphic
  to `R × R`.
* `sphere_zero_h0_iso`: `H₀(S⁰; R) ≅ R × R`.

## Main statements

* `sphere_zero_homology_above_is_zero`: `H_k(S⁰; R) = 0` for every `k ≥ 1`.
-/

open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup

namespace Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

/-- The zero-dimensional sphere `S⁰ = {x ∈ EuclideanSpace ℝ (Fin 1) : ‖x‖ = 1}` is equivalent
to `Fin 2`. The equivalence `Fin 2 → S⁰` sends `0` to the pole `EuclideanSpace.single 0 1` and
`1` to `EuclideanSpace.single 0 (-1)`; it is bijective since the two poles differ at coordinate
`0`, and any `x` on the sphere satisfies `(x 0) ^ 2 = 1` and `x = EuclideanSpace.single 0 (x 0)`,
so `x` is one of the two poles. -/
noncomputable def sphere_zero_index_equiv :
    ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) ≃ Fin 2 := by
  refine Equiv.symm (Equiv.ofBijective
    (![⟨EuclideanSpace.single 0 (1:ℝ), by
          rw [mem_sphere_zero_iff_norm, EuclideanSpace.norm_eq, Fin.sum_univ_one]; simp⟩,
       ⟨EuclideanSpace.single 0 (-1:ℝ), by
          rw [mem_sphere_zero_iff_norm, EuclideanSpace.norm_eq, Fin.sum_univ_one]; simp⟩])
    ⟨?_, ?_⟩)
  · intro a b hab
    fin_cases a <;> fin_cases b <;> simp_all <;>
      (exfalso
       have h := congrArg (fun v : EuclideanSpace ℝ (Fin 1) => v 0) hab
       norm_num [PiLp.single_apply] at h)
  · rintro ⟨x, hx⟩
    rw [mem_sphere_zero_iff_norm, EuclideanSpace.norm_eq, Fin.sum_univ_one] at hx
    have hx0 : x 0 ^ 2 = 1 := by
      have := Real.sqrt_eq_one.mp hx
      simpa [Real.norm_eq_abs, sq_abs] using this
    have hxe : x = EuclideanSpace.single 0 (x 0) := by
      ext i
      fin_cases i
      simp
    have hx0' : x 0 * x 0 = 1 := by rw [← sq]; exact hx0
    rcases mul_self_eq_one_iff.mp hx0' with h | h
    · have hxval : x = EuclideanSpace.single 0 (1:ℝ) := by rw [hxe, h]
      subst hxval
      exact ⟨0, rfl⟩
    · have hxval : x = EuclideanSpace.single 0 (-1:ℝ) := by rw [hxe, h]
      subst hxval
      exact ⟨1, rfl⟩

variable {R : Type} [Ring R]

/-- The coproduct of copies of `R` indexed by the points of `S⁰` is isomorphic to `R × R`,
via the equivalence `S⁰ ≃ Fin 2` of `sphere_zero_index_equiv`. -/
noncomputable def sphere_zero_coprod_prod_iso :
    (∐ fun _ : ↥(TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)) =>
        (ModuleCat.of R R)) ≅ ModuleCat.of R (R × R) := by
  classical
  have e : ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) ≃ Fin 2 :=
    sphere_zero_index_equiv
  exact ModuleCat.coprodIsoDirectSum _ ≪≫
    (DirectSum.lequivCongrLeft R e).toModuleIso ≪≫
    ((DirectSum.linearEquivFunOnFintype R (Fin 2) (fun _ => R)) ≪≫ₗ
      LinearEquiv.finTwoArrow R R).toModuleIso

/-- `H₀(S⁰; R) ≅ R × R`: since `S⁰` is a finite, hence totally disconnected, two-point space,
its zeroth singular homology is the free module on its points
(`AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace`); the remaining
content is identifying that coproduct over the two-point index with `R × R`, via
`sphere_zero_coprod_prod_iso`. -/
noncomputable def sphere_zero_h0_iso :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
        (ModuleCat.of R R)).obj
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)) ≅
      ModuleCat.of R (R × R) := by
  haveI : Finite ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) := sphere_zero_finite
  haveI : TotallyDisconnectedSpace (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)) :=
    inferInstance
  have h1 :
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
          (ModuleCat.of R R)).obj
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)) ≅
        ∐ fun _ : ↥(TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1)) =>
          (ModuleCat.of R R) :=
    AlgebraicTopology.singularHomologyFunctorZeroOfTotallyDisconnectedSpace
      (ModuleCat.{0} R) (ModuleCat.of R R)
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))
  have h2 := sphere_zero_coprod_prod_iso (R := R)
  exact h1 ≪≫ h2

/-- **Vanishing of higher homology of `S⁰`**: `H_k(S⁰; R) = 0` for every `k ≥ 1`, since `S⁰`
is totally disconnected (`sphere_zero_totally_disconnected`), and Mathlib's
`isZero_singularHomologyFunctor_of_totallyDisconnectedSpace` gives the vanishing directly for
every degree `k ≠ 0`. -/
theorem sphere_zero_homology_above_is_zero (k : ℕ) (hk : 1 ≤ k) :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj (TopCat.sphere 0)) := by
  haveI : TotallyDisconnectedSpace (TopCat.sphere 0) := sphere_zero_totally_disconnected
  exact AlgebraicTopology.isZero_singularHomologyFunctor_of_totallyDisconnectedSpace
    (ModuleCat.{0} R) k (ModuleCat.of R R) (TopCat.sphere 0) (by omega)

end Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
