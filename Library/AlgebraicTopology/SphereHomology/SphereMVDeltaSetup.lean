import Mathlib.Topology.Category.TopCat.Sphere
import Library.AlgebraicTopology.MayerVietoris.LongExactSequence
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand

/-!
# Mayer–Vietoris setup for sphere homology

This file assembles the pieces needed to run a Mayer–Vietoris induction on the singular
homology of spheres: an explicit open cover of `Sⁿ⁺²` by two polar caps, finiteness and total
disconnectedness of `S⁰`, the dimension-drop isomorphism identifying the homology of the
equatorial band with that of a lower sphere, and the fact that the Mayer–Vietoris connecting
map is an isomorphism (mono + epi) once the flanking pair-term homology groups vanish.

## Main definitions

* `band_singular_homology_iso_lower_sphere`: the singular homology of the open band between
  the two polar caps of `Sⁿ⁺²` is isomorphic to the singular homology of `Sⁿ⁺¹`.

## Main statements

* `sphere_cover_open_union`: the two polar caps `{x | x_{n+1} ≠ -1}` and `{x | x_{n+1} ≠ 1}` of
  `Sⁿ⁺²` are open and cover the sphere.
* `sphere_zero_finite`: `S⁰`, the unit sphere in `ℝ¹`, is a finite two-point set.
* `sphere_zero_totally_disconnected`: `S⁰` is totally disconnected.
* `mv_delta_isIso`: the Mayer–Vietoris connecting map is an isomorphism when the two flanking
  pair-term homology groups vanish.
* `mv_delta_mono`: the Mayer–Vietoris connecting map is mono when the incoming pair-term
  homology group vanishes.
-/

open CategoryTheory
open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.LongExactSequence
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand

namespace Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup

/-- The two polar caps `{x | x_{n+1} ≠ -1}` and `{x | x_{n+1} ≠ 1}` of the sphere
`Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1`, obtained by deleting one pole each, are
both open and their union is the whole sphere. Openness follows since each is the preimage of
`{y | y ≠ ±1}` (open by `isOpen_ne`) under the continuous last-coordinate projection; the union
covers everything because no point has last coordinate equal to both `-1` and `1`. -/
theorem sphere_cover_open_union (n : ℕ) :
    IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ -1} ∧
    IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ 1} ∧
    {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ -1} ∪
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ 1} = Set.univ := by
  have hc : Continuous fun x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 =>
      x.1 (Fin.last (n + 1)) :=
    (EuclideanSpace.proj (Fin.last (n + 1))).continuous.comp continuous_subtype_val
  refine ⟨hc.isOpen_preimage {y | y ≠ -1} isOpen_ne,
      hc.isOpen_preimage {y | y ≠ 1} isOpen_ne, ?_⟩
  ext x
  simp only [Set.mem_union, Set.mem_setOf_eq, Set.mem_univ, iff_true]
  by_contra h
  simp only [not_or, not_ne_iff] at h
  exact absurd (h.1.symm.trans h.2) (by norm_num)

/-- The unit sphere `S⁰` in `EuclideanSpace ℝ (Fin 1)` is finite: every point `x` on the sphere
has `‖x‖ = 1`, and since in dimension one `‖x‖ = |x 0|`, this forces `x 0 = ±1`, so `x` is one
of the two points `EuclideanSpace.single 0 1` or `EuclideanSpace.single 0 (-1)`. -/
theorem sphere_zero_finite :
    Finite ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) := by
  rw [Set.finite_coe_iff]
  apply Set.Finite.subset ((Set.finite_singleton (EuclideanSpace.single 0 (-1 : ℝ))).insert
    (EuclideanSpace.single 0 (1 : ℝ)))
  intro x hx
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
  · rw [hxe, h]; left; rfl
  · rw [hxe, h]; right; rfl

/-- `S⁰`, viewed as `TopCat.sphere 0`, is totally disconnected. This transports the total
disconnectedness of the finite (hence discrete) real sphere (`sphere_zero_finite`) across the
homeomorphism with `ULift` that identifies `TopCat.sphere 0`. -/
theorem sphere_zero_totally_disconnected :
    TotallyDisconnectedSpace (TopCat.sphere 0) := by
  have hfin : Finite ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) := sphere_zero_finite
  haveI := hfin
  have h : TotallyDisconnectedSpace ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1) :=
    inferInstance
  exact Homeomorph.ulift.isEmbedding.isTotallyDisconnected_range.mp (by
    rw [Homeomorph.range_coe]
    exact (totallyDisconnectedSpace_iff _).mp h)

/-- The dimension-drop isomorphism used in the sphere-homology induction: the singular
homology of the open band `{x ∈ Sⁿ⁺² | x_{n+1} ≠ ±1}` between the two polar caps is
isomorphic, in every degree `k`, to the singular homology of `Sⁿ⁺¹`. This follows because the
band is homotopy equivalent to its equator (`sphere_band_equator_hequiv`), which is
homeomorphic to `Sⁿ⁺¹` (`sphere_equator_homeo`), and singular homology is a homotopy
invariant. -/
noncomputable def band_singular_homology_iso_lower_sphere
    {R : Type} [Ring R] (n k : ℕ) :
    (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj
        (TopCat.of ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
          x.1 (Fin.last (n + 1)) ≠ 1 ∧ x.1 (Fin.last (n + 1)) ≠ -1})) ≅
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 1))) 1))) :=
  homotopy_equiv_singular_homology_iso
    ((sphere_band_equator_hequiv n).trans (sphere_equator_homeo n).toHomotopyEquiv) k

section MvDelta

variable {R : Type} [Ring R] {X : TopCat.{0}} {A B : Set X}
    (hA : IsOpen A) (hB : IsOpen B) (hAB : A ∪ B = Set.univ) (n : ℕ)

/-- **The Mayer–Vietoris connecting map is an isomorphism**: for an open cover `X = A ∪ B`,
the connecting map `mv_delta` in degree `n` is an isomorphism of `R`-modules provided the two
flanking pair-term homology groups vanish, i.e. `H_{n+1}(C(A) ⊕ C(B)) = 0` (`hz1`) and
`H_n(C(A) ⊕ C(B)) = 0` (`hz2`). The map is mono by exactness of the total long exact sequence
together with `hz1`, and epi by exactness of the intersection long exact sequence together
with `hz2`; mono + epi gives an isomorphism in the balanced category `ModuleCat R`. -/
theorem mv_delta_isIso
    (hz1 : IsZero
        ((mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)
          (singular_subcomplex_of_set X B)).X₂.homology (n + 1)))
    (hz2 : IsZero
        ((mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)
          (singular_subcomplex_of_set X B)).X₂.homology n)) :
    IsIso (mv_delta (R := R) hA hB hAB n) := by
  haveI : QuasiIso (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj X)
      (le_top : singular_subcomplex_of_set X A ⊔ singular_subcomplex_of_set X B ≤ ⊤)) :=
    mv_incl_quasi_iso hA hB hAB
  haveI hmono : Mono (mv_delta (R := R) hA hB hAB n) :=
    (mv_les_exact_total (R := R) hA hB hAB n).mono_g (hz1.eq_of_src _ _)
  haveI hepi : Epi (mv_delta (R := R) hA hB hAB n) :=
    (mv_les_exact_inter (R := R) hA hB hAB n).epi_f (hz2.eq_of_tgt _ _)
  exact isIso_of_mono_of_epi _

/-- The Mayer–Vietoris connecting map `mv_delta` is mono whenever the incoming pair-term
homology group `H_{n+1}(C(A) ⊕ C(B))` vanishes (`hpair`), by exactness of the total long exact
sequence at that spot. -/
theorem mv_delta_mono
    (hpair : IsZero
      (((mv_short_complex (R := R) (TopCat.toSSet.obj X)
          (singular_subcomplex_of_set X A)
          (singular_subcomplex_of_set X B)).X₂).homology (n + 1))) :
    Mono (mv_delta (R := R) hA hB hAB n) := by
  exact (mv_les_exact_total (R := R) hA hB hAB n).mono_g (hpair.eq_of_src _ _)

end MvDelta

end Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
