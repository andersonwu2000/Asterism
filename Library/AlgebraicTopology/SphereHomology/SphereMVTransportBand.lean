import Library.AlgebraicTopology.MayerVietoris.LongExactSequence
import Library.AlgebraicTopology.SphereHomology.SubspaceSupportedNaturality
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Transporting the H₀ intersection-inclusion naturality square across the band bridge

The intersection of the two open hemispheres of a sphere used in a Mayer–Vietoris cover can be
described either as `subcomplex(U₊) ⊓ subcomplex(U₋)` or, via the substitution
`x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1`, as the subcomplex supported on a
single "band" set. `inter_supported_homology_iso_band` bridges the two descriptions on
homology; this file transports the H₀ naturality square for the intersection-inclusion map
across that bridge.

## Main statements

* `inter_band_iso_hom_eq`: unfolds `inter_supported_homology_iso_band`'s `.hom` as the composite
  of the connecting `eqToHom` with `subspace_supported_homology_iso`'s `.hom`.
* `supported_chain_incl_congr_left`: rewrites the `homologyMap` of a subcomplex inclusion along a
  substitution of the source subcomplex by a propositionally equal one.
* `inter_supported_homology_iso_band_naturality`: the H₀ intersection-inclusion naturality
  square, transported across the `⊓ → band` bridge.
-/

open CategoryTheory
open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.LongExactSequence
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SubspaceSupportedNaturality
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.SphereMVTransportBand

variable {R : Type} [Ring R]

/-- Unfold both sides to `inter_supported_homology_iso_band`'s definitional trans-of-isos:
`inter_supported_homology_iso_band` is built as `eqToIso hsub' ≪≫ subspace_supported_homology_iso
...`, so `Iso.trans_hom` splits `.hom` into the two factors, and the `eqToHom` legs agree by
proof irrelevance on the (defeq, `n + 1 + 1 = n + 2`) equality type. -/
theorem inter_band_iso_hom_eq (n : ℕ)
    (hsub :
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 | x.1 (Fin.last (n + 2)) ≠ -1} ⊓
        singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 | x.1 (Fin.last (n + 2)) ≠ 1} =
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
            x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1}) :
    (inter_supported_homology_iso_band (R := R) (n + 1) 0).hom
      = eqToHom (congrArg (fun s => (supported_chain_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1)))
            s).homology 0) hsub)
        ≫ (subspace_supported_homology_iso (R := R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
            {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
              x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1} 0).hom := by
  unfold inter_supported_homology_iso_band
  rw [Iso.trans_hom]
  congr 1

/-- `eqToHom_refl` and `id_comp` after substituting `hAA : A = A'`: once `A = A'` is substituted,
`hAB` and `hA'B` are proofs of the same proposition `A ≤ B` (proof irrelevance), so both
`homologyMap`s are the same term and the `eqToHom` collapses to the identity. -/
theorem supported_chain_incl_congr_left
    (X : SSet.{0}) {A A' B : X.Subcomplex} (hAA : A = A') (hAB : A ≤ B) (hA'B : A' ≤ B) (k : ℕ) :
    HomologicalComplex.homologyMap (supported_chain_complex_incl (R := R) X hAB) k
      = eqToHom (congrArg (fun s => (supported_chain_complex (R := R) X s).homology k) hAA)
        ≫ HomologicalComplex.homologyMap (supported_chain_complex_incl (R := R) X hA'B) k := by
  subst hAA
  simp only [CategoryTheory.eqToHom_refl, CategoryTheory.Category.id_comp]

/-- Transport the H₀ intersection-inclusion naturality square across the `⊓ → band` subcomplex
bridge. The core is `subspace_supported_homology_iso_naturality` (band ↪ U₊); the goal differs
only by the propositional subcomplex equality `hsub : subcomplex (U₊) ⊓ subcomplex (U₋) =
subcomplex (band)` (via `singular_subcomplex_inf_eq` and `and_comm`), which induces the same
`eqToHom e` on both legs: `hA` (`supported_chain_incl_congr_left`) rewrites the LHS
inclusion-`homologyMap`, `hC` (`inter_band_iso_hom_eq`) unfolds the RHS band bridge, and the
shared `eqToHom e` cancels after the naturality square, closing by associativity. -/
theorem inter_supported_homology_iso_band_naturality (n : ℕ)
    (h : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
          x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1} ⊆
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
          x.1 (Fin.last (n + 2)) ≠ -1}) :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1)))
            (inf_le_left :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
                    x.1 (Fin.last (n + 2)) ≠ -1} ⊓
                singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
                    x.1 (Fin.last (n + 2)) ≠ 1} ≤
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
                    x.1 (Fin.last (n + 2)) ≠ -1})) 0
        ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
                x.1 (Fin.last (n + 2)) ≠ -1} 0).hom
      = (inter_supported_homology_iso_band (R := R) (n + 1) 0).hom
        ≫ ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
              (ModuleCat.of R R)).map
              (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩) := by
  set Sph := Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 with hSph
  have hsub :
      singular_subcomplex_of_set (TopCat.of Sph) {x : Sph | x.1 (Fin.last (n + 2)) ≠ -1} ⊓
        singular_subcomplex_of_set (TopCat.of Sph) {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1} =
      singular_subcomplex_of_set (TopCat.of Sph)
          {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1} := by
    rw [singular_subcomplex_inf_eq]
    congr 1
    ext x
    exact and_comm
  have hle_band :
      singular_subcomplex_of_set (TopCat.of Sph)
          {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1} ≤
        singular_subcomplex_of_set (TopCat.of Sph) {x : Sph | x.1 (Fin.last (n + 2)) ≠ -1} :=
    hsub ▸ inf_le_left
  have hnat := subspace_supported_homology_iso_naturality (R := R) (TopCat.of Sph) h 0 hle_band
  have e :
      (supported_chain_complex (R := R) (TopCat.toSSet.obj (TopCat.of Sph))
          (singular_subcomplex_of_set (TopCat.of Sph) {x : Sph | x.1 (Fin.last (n + 2)) ≠ -1} ⊓
            singular_subcomplex_of_set (TopCat.of Sph)
              {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1})).homology 0
        = (supported_chain_complex (R := R) (TopCat.toSSet.obj (TopCat.of Sph))
            (singular_subcomplex_of_set (TopCat.of Sph)
              {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1})).homology 0 :=
    congrArg
      (fun s =>
        (supported_chain_complex (R := R) (TopCat.toSSet.obj (TopCat.of Sph)) s).homology 0)
      hsub
  have hA :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj (TopCat.of Sph))
            (inf_le_left :
              singular_subcomplex_of_set (TopCat.of Sph)
                  {x : Sph | x.1 (Fin.last (n + 2)) ≠ -1} ⊓
                singular_subcomplex_of_set (TopCat.of Sph)
                  {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1} ≤
              singular_subcomplex_of_set (TopCat.of Sph)
                  {x : Sph | x.1 (Fin.last (n + 2)) ≠ -1})) 0
        = eqToHom e ≫ HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R) (TopCat.toSSet.obj (TopCat.of Sph))
              hle_band) 0 :=
    supported_chain_incl_congr_left (R := R) (TopCat.toSSet.obj (TopCat.of Sph))
      hsub inf_le_left hle_band 0
  have hC :
      (inter_supported_homology_iso_band (R := R) (n + 1) 0).hom
        = eqToHom e ≫ (subspace_supported_homology_iso (R := R) (TopCat.of Sph)
            {x : Sph | x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1} 0).hom :=
    inter_band_iso_hom_eq (R := R) n hsub
  rw [hA, hC]
  simp only [Category.assoc]
  rw [hnat]
  exact (Category.assoc _ _ _).symm

end Library.AlgebraicTopology.SphereHomology.SphereMVTransportBand
