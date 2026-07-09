import Mathlib
import Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso

-- circle_pair_h0_iso: MV pair term at degree 0 for the circle's two caps ≅ R × R.
-- `mv_pair_homology_biprod_iso` splits H₀(X₂) as H₀(U+) ⊞ H₀(U−); both caps are
-- contractible (`pole_cap_contractible 0 (∓1)`) hence path-connected, so
-- `TopCat.singularHomology₀ε` gives each factor ≅ R; `ModuleCat.biprodIsoProd`
-- identifies the resulting biproduct with the R × R module.
noncomputable def circle_pair_h0_iso {R : Type} [Ring R] :
    (mv_short_complex (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x | x.1 (Fin.last 1) ≠ -1})
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x | x.1 (Fin.last 1) ≠ 1})).X₂.homology 0 ≅ ModuleCat.of R (R × R) := by
  haveI hA : ContractibleSpace
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ -1} :=
    pole_cap_contractible 0 (-1) (Or.inr rfl)
  haveI hB : ContractibleSpace
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ 1} :=
    pole_cap_contractible 0 1 (Or.inl rfl)
  exact (mv_pair_homology_biprod_iso (R := R)
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
        {x | x.1 (Fin.last 1) ≠ -1} {x | x.1 (Fin.last 1) ≠ 1} 0) ≪≫
      biprod.mapIso
        (CategoryTheory.asIso (TopCat.singularHomology₀ε
          (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ -1})) (ModuleCat.of R R)))
        (CategoryTheory.asIso (TopCat.singularHomology₀ε
          (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R))) ≪≫
      ModuleCat.biprodIsoProd (ModuleCat.of R R) (ModuleCat.of R R)

end Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
