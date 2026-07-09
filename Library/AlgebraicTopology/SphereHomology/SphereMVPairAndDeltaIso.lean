import Library.AlgebraicTopology.MayerVietoris.LongExactSequence
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Mayer–Vietoris pair-term vanishing and the connecting-map isomorphism for spheres

For the Mayer–Vietoris cover of `Sⁿ⁺¹` by the two caps `U₊` and `U₋` (the complements of the
south and north poles), this file shows that the pair term of the associated short complex has
vanishing homology in every positive degree, and deduces that the Mayer–Vietoris connecting map
is an isomorphism identifying `H_{k+1}(Sⁿ⁺¹)` with the homology of the equatorial band
`U₊ ∩ U₋` in every degree `k ≥ 1`.

## Main statements

* `mv_pair_homology_zero`: the pair term `(mv_short_complex …).X₂` has vanishing homology in
  every degree `j ≥ 1`, since it is the biproduct of the (contractible) caps' homologies.
* `sphere_mv_delta_iso`: the Mayer–Vietoris connecting map `mv_delta` induces an isomorphism
  `H_{k+1}(Sⁿ⁺¹) ≅ H_k(U₊ ∩ U₋)` for every `k ≥ 1`.
-/

open CategoryTheory
open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso

variable {R : Type} [Ring R] (n : ℕ)

/-- For the Mayer–Vietoris cover of `Sⁿ⁺¹` by the two caps `U₊` and `U₋` (complements of the
south and north poles), the pair term `(mv_short_complex …).X₂` — the biproduct of the two caps'
singular chain complexes — has vanishing homology in every degree `j ≥ 1`. Indeed
`mv_pair_homology_biprod_iso` identifies the degree-`j` homology of the pair term with
`H_j(U₊) ⊞ H_j(U₋)`, and both caps are contractible, so each summand vanishes for `j ≠ 0`. -/
theorem mv_pair_homology_zero (j : ℕ) (hj : 1 ≤ j) :
    IsZero
      ((mv_short_complex (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)))
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 | x.1 (Fin.last (n + 1)) ≠ -1})
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ 1})).X₂.homology j) := by
  have hj0 : j ≠ 0 := by omega
  obtain ⟨hcapS, hcapN⟩ := sphere_cap_contractible n
  have hzS : IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) j).obj
        (ModuleCat.of R R)).obj
        (TopCat.of ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ -1})) :=
    @contractible_singular_homology_is_zero R _
      (TopCat.of ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
          x.1 (Fin.last (n + 1)) ≠ -1}) hcapS j hj0
  have hzN : IsZero
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) j).obj
        (ModuleCat.of R R)).obj
        (TopCat.of ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ 1})) :=
    @contractible_singular_homology_is_zero R _
      (TopCat.of ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
          x.1 (Fin.last (n + 1)) ≠ 1}) hcapN j hj0
  refine IsZero.of_iso ?_
    (mv_pair_homology_biprod_iso (R := R)
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 | x.1 (Fin.last (n + 1)) ≠ -1}
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 | x.1 (Fin.last (n + 1)) ≠ 1}
      j)
  exact (biprod_isZero_iff _ _).mpr ⟨hzS, hzN⟩

/-- For the Mayer–Vietoris cover of `Sⁿ⁺¹` by the two contractible caps `U₊` and `U₋`, the
connecting map `mv_delta` is an isomorphism from `H_{k+1}(Sⁿ⁺¹)` to `H_k(U₊ ∩ U₋)` for every
`k ≥ 1`: it is mono since the pair term vanishes in degree `k + 1` and epi since it vanishes in
degree `k` (via `mv_delta_isIso`). Composing with `supported_top_homology_iso` (identifying the
total term with the sphere's homology) and `inter_supported_homology_iso_band` (identifying the
intersection term `U₊ ∩ U₋` with the equatorial band) yields the isomorphism. -/
noncomputable def sphere_mv_delta_iso (k : ℕ) (hk : 1 ≤ k) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) (k + 1)).obj
        (ModuleCat.of R R)).obj
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)) ≅
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj
          (TopCat.of {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
              x.1 (Fin.last (n + 1)) ≠ 1 ∧ x.1 (Fin.last (n + 1)) ≠ -1}) := by
  obtain ⟨hA, hB, hAB⟩ := sphere_cover_open_union n
  haveI : IsIso (Library.AlgebraicTopology.MayerVietoris.LongExactSequence.mv_delta
      (R := R) (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
      hA hB hAB k) :=
    mv_delta_isIso (R := R)
      (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
      hA hB hAB k (mv_pair_homology_zero n (k + 1) (by omega)) (mv_pair_homology_zero n k hk)
  exact (supported_top_homology_iso (R := R)
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)) (k + 1)).symm
    ≪≫ asIso (Library.AlgebraicTopology.MayerVietoris.LongExactSequence.mv_delta
        (R := R) (X := TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
        hA hB hAB k)
    ≪≫ inter_supported_homology_iso_band n k

end Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso
