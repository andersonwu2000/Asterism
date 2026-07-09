import Library.AlgebraicTopology.SphereHomology.SphereH0MonoFacts
import Library.AlgebraicTopology.SphereHomology.SphereMVConnectingMap
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Vanishing of the first singular homology of spheres

This file proves that the first singular homology group `H₁(Sⁿ⁺²; R)` of a sphere vanishes, by
exhibiting the Mayer–Vietoris connecting map `mv_delta` (on the standard polar cover) as the zero
map and combining this with the fact that it is a monomorphism.

## Main statements

* `sphere_h1_delta_eq_zero`: the Mayer–Vietoris connecting map `δ = mv_delta` from `H₁` of the
  cover's union to `H₀` of its intersection is the zero map, for the standard polar cover of a
  sphere.
* `sphere_homology_one_is_zero`: the first singular homology `H₁(Sⁿ⁺²; R)` is zero.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.LongExactSequence
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SphereH0MonoFacts
open Library.AlgebraicTopology.SphereHomology.SphereMVConnectingMap
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.SphereH1Vanishing

variable {R : Type} [Ring R] (n : ℕ)

/-- The Mayer–Vietoris connecting map `δ = mv_delta`, from `H₁` of the union `A ∪ B` down to
`H₀` of the intersection `A ∩ B`, is the zero map for the polar cover
`A = {x | x_last ≠ -1}`, `B = {x | x_last ≠ 1}` of a sphere. This follows from Mayer–Vietoris
exactness at the intersection spot: the composite `δ ≫ H₀(C(A ∩ B) → C(A) ⊕ C(B))` vanishes
(`delta_comp_inter_incl_zero`), and that `H₀` map is mono (`inter_incl_h0_mono`, since the
band/cap pieces are path-connected), so a mono postcomposed to zero forces `δ` itself to be
zero (`cancel_mono`). -/
theorem sphere_h1_delta_eq_zero
    (hA : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ -1})
    (hB : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1})
    (hAB : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1} ∪
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ 1} = Set.univ) :
    mv_delta (R := R) (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
      hA hB hAB 0 = 0 := by
  have h1 : mv_delta (R := R)
        (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
        hA hB hAB 0
      ≫ HomologicalComplex.homologyMap
          (mv_short_complex (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ -1})
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ 1})).f 0 = 0 :=
    delta_comp_inter_incl_zero (R := R) n hA hB hAB
  haveI h2 : CategoryTheory.Mono
        (HomologicalComplex.homologyMap
          (mv_short_complex (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ -1})
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ 1})).f 0) :=
    inter_incl_h0_mono (R := R) n hA hB hAB
  exact (cancel_mono _).mp (h1.trans (zero_comp).symm)

/-- **Vanishing of first sphere homology**: the first singular homology `H₁(Sⁿ⁺²; R)` of the
`(n+2)`-sphere is zero. The proof decomposes `H₁` through the Mayer–Vietoris connecting map
`δ = mv_delta` on the standard polar cover (`U₊`, `U₋` open, union `univ`): `δ` is mono
(`sphere_h1_delta_mono`, since the pair term `H₁(C(A) ⊕ C(B))` vanishes because the caps are
contractible) and `δ = 0` (`sphere_h1_delta_eq_zero`), so a mono equal to zero forces its source
to be zero; transporting across `supported_top_homology_iso` gives the vanishing of the packaged
singular `H₁`. -/
theorem sphere_homology_one_is_zero :
    CategoryTheory.Limits.IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 1).obj
          (ModuleCat.of R R)).obj
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))) := by
  let X : TopCat.{0} := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)
  have hcov := sphere_cover_open_union (n+1)
  have hA : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
      x.1 (Fin.last (n+2)) ≠ -1} := hcov.1
  have hB : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
      x.1 (Fin.last (n+2)) ≠ 1} := hcov.2.1
  have hAB : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ -1} ∪
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1} = Set.univ := hcov.2.2
  have hzero : mv_delta (R := R) (X := X) hA hB hAB 0 = 0 :=
    sphere_h1_delta_eq_zero n hA hB hAB
  have hmono : Mono (mv_delta (R := R) (X := X) hA hB hAB 0) :=
    sphere_h1_delta_mono n hA hB hAB
  haveI := hmono
  have hZ : IsZero ((supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).homology 1) :=
    IsZero.of_mono_eq_zero (mv_delta (R := R) (X := X) hA hB hAB 0) hzero
  exact hZ.of_iso (supported_top_homology_iso (R := R) X 1).symm

end Library.AlgebraicTopology.SphereHomology.SphereH1Vanishing
