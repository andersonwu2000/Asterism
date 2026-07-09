import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SphereH1Vanishing
import Library.AlgebraicTopology.SphereHomology.SphereSuspensionIso
import Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

/-!
# Vanishing range of sphere homology

This file collects the vanishing statements for the singular homology of spheres
`TopCat.sphere n` outside the fundamental degree `k = n`: the homology module
`H_k(Sⁿ; R)` is zero whenever `k ≠ n` (for `n ≥ 1`). The proof proceeds by
suspension descent, transporting vanishing across the suspension isomorphism
`sphere_suspension_homology_iso` down to the base cases `sphere_zero_homology_above_is_zero`
(degree `0` sphere) and `sphere_homology_one_is_zero` (degree-`1` homology, via the
Mayer-Vietoris boundary map).

## Main statements

* `sphere_homology_above_dim_is_zero`: `H_k(Sⁿ; R) = 0` for `n < k`.
* `sphere_h1_topcat_is_zero`: `H_1(Sⁿ; R) = 0` for `n ≥ 2`.
* `sphere_homology_below_dim_is_zero`: `H_k(Sⁿ; R) = 0` for `1 ≤ k < n`.
* `sphere_homology_eq_zero_of_ne`: `H_k(Sⁿ; R) = 0` for `k ≠ n` (`n ≥ 1`, `k ≠ 0`).
-/

open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SphereH1Vanishing
open Library.AlgebraicTopology.SphereHomology.SphereSuspensionIso
open Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

namespace Library.AlgebraicTopology.SphereHomology.SphereHomologyVanishingRange

variable {R : Type} [Ring R]

/-- Above the dimension of the sphere (`n < k`), the homology module `H_k(Sⁿ; R)` vanishes.
The proof is an induction on `n` via suspension descent: the base case `n = 0` is
`sphere_zero_homology_above_is_zero`, and the successor step transports the inductive
hypothesis at `H_j(Sᵐ; R)` (with `m < j`) across the suspension isomorphism
`sphere_suspension_homology_iso` to `H_{j+1}(Sᵐ⁺¹; R)`. -/
theorem sphere_homology_above_dim_is_zero (n k : ℕ) (hkn : n < k) :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj (TopCat.sphere n)) := by
  induction n generalizing k with
  | zero =>
    exact sphere_zero_homology_above_is_zero k (by omega)
  | succ m ih =>
    obtain ⟨j, rfl⟩ : ∃ j, k = j + 1 := ⟨k - 1, by omega⟩
    have hj1 : 1 ≤ j := by omega
    have hmj : m < j := by omega
    exact CategoryTheory.Limits.IsZero.of_iso (ih j hmj)
      (sphere_suspension_homology_iso m j hj1)

/-- The first homology module `H_1(Sⁿ; R)` vanishes for `n ≥ 2`. This is the base case of
`sphere_homology_below_dim_is_zero`: it transports `sphere_homology_one_is_zero`
(vanishing of `H_1(Sᵐ⁺²; R)` via the Mayer-Vietoris boundary map) across the homotopy
equivalence between the `ULift` of the bare `Metric.sphere` and the packaged
`TopCat.sphere n`. -/
theorem sphere_h1_topcat_is_zero (n : ℕ) (hn : 2 ≤ n) :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 1).obj
          (ModuleCat.of R R)).obj (TopCat.sphere n)) := by
  obtain ⟨m, rfl⟩ : ∃ m, n = m + 2 := ⟨n - 2, by omega⟩
  have eu := Homeomorph.ulift (X := Metric.sphere (0 : EuclideanSpace ℝ (Fin (m + 3))) 1)
  have hZ := sphere_homology_one_is_zero (R := R) m
  exact hZ.of_iso (homotopy_equiv_singular_homology_iso eu.toHomotopyEquiv 1)

/-- Below the dimension of the sphere (`1 ≤ k < n`), the homology module `H_k(Sⁿ; R)`
vanishes. The proof is an induction on `k` via suspension descent: the base case
`k = 1` is `sphere_h1_topcat_is_zero`, and the successor step (`k = j + 1 ≥ 2`)
transports the inductive hypothesis at `H_j(Sᵐ; R)` (with `j < m`) across the
suspension isomorphism `sphere_suspension_homology_iso` to `H_{j+1}(Sᵐ⁺¹; R)`. -/
theorem sphere_homology_below_dim_is_zero (n k : ℕ) (hk : 1 ≤ k) (hkn : k < n) :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj (TopCat.sphere n)) := by
  induction k generalizing n with
  | zero => omega
  | succ j ih =>
    obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := ⟨n - 1, by omega⟩
    rcases Nat.eq_zero_or_pos j with hj | hj
    · subst hj
      exact sphere_h1_topcat_is_zero (m + 1) (by omega)
    · exact (ih m hj (by omega)).of_iso (sphere_suspension_homology_iso m j hj)

/-- **Vanishing of sphere homology off the fundamental degree**: for a sphere `Sⁿ`
with `n ≥ 1`, the homology module `H_k(Sⁿ; R)` vanishes whenever `k ≠ n` (and `k ≠ 0`).
This combines `sphere_homology_below_dim_is_zero` (case `k < n`) with
`sphere_homology_above_dim_is_zero` (case `n < k`). -/
theorem sphere_homology_eq_zero_of_ne (n k : ℕ) (_hn : 1 ≤ n) (hk0 : k ≠ 0) (hkn : k ≠ n) :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj (TopCat.sphere n)) := by
  rcases lt_or_gt_of_ne hkn with h | h
  · exact sphere_homology_below_dim_is_zero n k (Nat.one_le_iff_ne_zero.mpr hk0) h
  · exact sphere_homology_above_dim_is_zero n k h

end Library.AlgebraicTopology.SphereHomology.SphereHomologyVanishingRange
