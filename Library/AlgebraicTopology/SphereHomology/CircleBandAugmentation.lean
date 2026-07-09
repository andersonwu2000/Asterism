import Library.AlgebraicTopology.SphereHomology.CoprodDescAndTDBasics
import Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
import Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

/-!
# The augmentation on the equatorial band of the 2-sphere

This file identifies the singular `H₀` augmentation map on the open equatorial band of the
2-sphere `S²` (the points whose last coordinate is neither `1` nor `-1`) with the coordinate-sum
map `R × R → R`, transported along the isomorphism between the band and the `0`-sphere `S⁰`.

## Main statements

* `circle_band_augmentation_eq`: the augmentation map on the band, viewed through the
  band-to-`S⁰` and `S⁰`-to-`R × R` isomorphisms, is the sum of the two coordinate projections.
* `band_aug_coord_sum`: an alias of `circle_band_augmentation_eq`, kept because the two statements
  were minted independently (from the same underlying fact) before inject-time deduplication could
  link them.
-/

open CategoryTheory
open Library.AlgebraicTopology.SphereHomology.CoprodDescAndTDBasics
open Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
open Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology

namespace Library.AlgebraicTopology.SphereHomology.CircleBandAugmentation

variable {R : Type} [Ring R]

/-- The singular `H₀` augmentation map on the equatorial band of `S²` — the subspace of
`Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1` avoiding the two poles — agrees, through the
isomorphism with the `0`-sphere, with the sum of the two coordinate projections `R × R → R`. -/
theorem circle_band_augmentation_eq :
    TopCat.singularHomology₀ε
        (TopCat.of ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1})
        (ModuleCat.of R R)
      = (band_singular_homology_iso_lower_sphere (R := R) 0 0 ≪≫
            sphere_zero_h0_iso (R := R)).hom ≫
          ModuleCat.ofHom (LinearMap.fst R R R + LinearMap.snd R R R) := by
  have hs0 : TopCat.singularHomology₀ε
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 1)) 1))
        (ModuleCat.of R R)
      = (sphere_zero_h0_iso (R := R)).hom ≫
          ModuleCat.ofHom (LinearMap.fst R R R + LinearMap.snd R R R) :=
    sphere_zero_augmentation_eq (R := R)
  rw [Iso.trans_hom, Category.assoc, ← hs0]
  exact (singular_h0_augmentation_naturality
    (TopCat.ofHom ((sphere_band_equator_hequiv 0).trans
      (sphere_equator_homeo 0).toHomotopyEquiv).toFun)).symm

alias band_aug_coord_sum := circle_band_augmentation_eq

end Library.AlgebraicTopology.SphereHomology.CircleBandAugmentation
