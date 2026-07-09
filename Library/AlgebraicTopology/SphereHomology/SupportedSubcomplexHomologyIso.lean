import Mathlib.Analysis.InnerProductSpace.PiL2
import Library.AlgebraicTopology.MayerVietoris.LongExactSequence
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexDifferential

/-!
# Homology of supported subcomplexes and the sphere Mayer–Vietoris dictionary

This file identifies the homology of an `A`-supported singular subcomplex with the singular
homology of the subspace `A`, and uses this bridge to translate each term of the
Mayer–Vietoris short complex for a sphere covered by two bands into mathlib's
`singularHomologyFunctor` spelling.

## Main definitions

* `subspace_supported_homology_iso`: for `A : Set X`, the degree-`k` homology of the
  `A`-supported subcomplex of the singular chain complex of `X` is isomorphic to the singular
  homology of `A`.
* `mv_pair_homology_biprod_iso`: the degree-`j` homology of the biproduct term `X₂` of the
  Mayer–Vietoris short complex for `A` and `B` splits as the biproduct of the singular
  homologies of `A` and `B`.
* `supported_top_homology_iso`: the `⊤`-supported twin of `subspace_supported_homology_iso`,
  identifying the total supported-subcomplex homology with the singular homology of `X`.
* `inter_supported_homology_iso_band`: identifies the degree-`k` homology of the
  Mayer–Vietoris short complex's intersection term `X₁`, for the sphere covered by the bands
  where the last coordinate is `≠ -1` and `≠ 1`, with the singular homology of the intersection
  band where the last coordinate is `≠ 1 ∧ ≠ -1`.

## Main statements

* `singular_subcomplex_inf_eq`: the infimum of two singular subcomplexes supported on `A` and
  `B` equals the singular subcomplex supported on `A ∩ B`.

## Implementation notes

None of these isomorphisms carries new mathematical content: each composes an already-proved
chain-complex isomorphism with `HomologicalComplex.homologyFunctor.mapIso` (or
`Functor.mapBiprod` / `biprod.mapIso`) with the packaged identification
`singular_homology_iso_chain_homology` between the two chain-homology spellings. They exist so
that downstream Mayer–Vietoris term conversions have a single interface to cite.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexDifferential

namespace Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-- The degree-`k` homology of the `A`-supported subcomplex of the singular chain complex of
`X` is isomorphic to the singular homology of the subspace `A`. Obtained by applying
`HomologicalComplex.homologyFunctor.mapIso` to the chain-complex isomorphism
`subspace_supported_chain_complex_iso`, then composing with
`singular_homology_iso_chain_homology` to land in mathlib's `singularHomologyFunctor` spelling.
This is the interface every downstream Mayer–Vietoris term conversion cites to identify the
supported-subcomplex homology with the singular homology of the subspace `TopCat.of A`. -/
noncomputable def subspace_supported_homology_iso {R : Type} [Ring R]
    (X : TopCat.{0}) (A : Set X) (k : ℕ) :
    (supported_chain_complex (R := R) (TopCat.toSSet.obj X)
        (singular_subcomplex_of_set X A)).homology k ≅
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj (TopCat.of A) :=
  (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) k).mapIso
      (subspace_supported_chain_complex_iso (R := R) X A)
    ≪≫ (singular_homology_iso_chain_homology (TopCat.of A) k).symm

/-- The infimum of the `A`- and `B`-supported singular subcomplexes of `X` equals the
`(A ∩ B)`-supported singular subcomplex. -/
theorem singular_subcomplex_inf_eq (X : TopCat.{0}) (A B : Set X) :
    singular_subcomplex_of_set X A ⊓ singular_subcomplex_of_set X B =
      singular_subcomplex_of_set X (A ∩ B) := by
  ext n σ
  simp only [singular_subcomplex_of_set, CategoryTheory.Subfunctor.min_obj, Set.mem_inter_iff,
    Set.mem_setOf_eq, Set.subset_inter_iff]

/-- The degree-`j` homology of the Mayer–Vietoris pair term `X₂` (the biproduct of the
`A`- and `B`-supported subcomplexes) splits as the biproduct of the singular homologies of
`A` and `B`. The homology functor is additive, hence preserves the binary biproduct
`X₂ = C(A) ⊞ C(B)` via `Functor.mapBiprod`; `biprod.mapIso` then applies
`subspace_supported_homology_iso` on each factor. -/
noncomputable def mv_pair_homology_biprod_iso {R : Type} [Ring R]
    (X : TopCat.{0}) (A B : Set X) (j : ℕ) :
    ((mv_short_complex (R := R) (TopCat.toSSet.obj X)
        (singular_subcomplex_of_set X A)
        (singular_subcomplex_of_set X B)).X₂).homology j ≅
      biprod
        (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) j).obj
          (ModuleCat.of R R)).obj (TopCat.of ↥A))
        (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) j).obj
          (ModuleCat.of R R)).obj (TopCat.of ↥B)) :=
  haveI : PreservesBinaryBiproducts
      (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) j) :=
    preservesBinaryBiproducts_of_preservesBiproducts _
  (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) j).mapBiprod _ _
    ≪≫ biprod.mapIso
        (subspace_supported_homology_iso (R := R) X A j)
        (subspace_supported_homology_iso (R := R) X B j)

/-- The `⊤`-supported twin of `subspace_supported_homology_iso`: the degree-`k` homology of the
`⊤`-supported subcomplex of the singular chain complex of `X` is isomorphic to the singular
homology of `X`. Obtained by applying `HomologicalComplex.homologyFunctor.mapIso` to
`chain_complex_top_iso` (identifying the `⊤`-supported subcomplex with mathlib's
`X.chainComplex`), then composing with `singular_homology_iso_chain_homology`. Downstream
Mayer–Vietoris term conversions cite this once to identify the total supported-subcomplex
homology with the singular homology of `X`. -/
noncomputable def supported_top_homology_iso {R : Type} [Ring R]
    (X : TopCat.{0}) (k : ℕ) :
    (supported_chain_complex (R := R) (TopCat.toSSet.obj X) ⊤).homology k ≅
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj X :=
  (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) k).mapIso
      (Library.AlgebraicTopology.MayerVietoris.LongExactSequence.chain_complex_top_iso
        (R := R) (TopCat.toSSet.obj X))
    ≪≫ (singular_homology_iso_chain_homology X k).symm

/-- The intersection-term conversion of the Mayer–Vietoris dictionary for the sphere: the
Mayer–Vietoris short complex's `X₁` term is the subcomplex supported on the intersection of
the bands where the last coordinate is `≠ -1` and `≠ 1`; its degree-`k` homology is isomorphic
to the singular homology of the band where the last coordinate is `≠ 1 ∧ ≠ -1`. The
isomorphism `eqToIso`-bridges `X₁.homology k` to the band-supported homology via
`singular_subcomplex_inf_eq` together with `and_comm` (normalizing the swapped conjunction
order), then applies `subspace_supported_homology_iso`. -/
noncomputable def inter_supported_homology_iso_band {R : Type} [Ring R] (n k : ℕ) :
    ((mv_short_complex (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1)))
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ -1})
        (singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ 1})).X₁).homology k ≅
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
          (ModuleCat.of R R)).obj
          (TopCat.of {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
              x.1 (Fin.last (n + 1)) ≠ 1 ∧ x.1 (Fin.last (n + 1)) ≠ -1}) := by
  refine eqToIso ?_ ≪≫ subspace_supported_homology_iso (R := R)
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
        x.1 (Fin.last (n + 1)) ≠ 1 ∧ x.1 (Fin.last (n + 1)) ≠ -1} k
  congr 1
  have hsub :
      singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ -1} ⊓
        singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ 1} =
      singular_subcomplex_of_set
          (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1 |
            x.1 (Fin.last (n + 1)) ≠ 1 ∧ x.1 (Fin.last (n + 1)) ≠ -1} := by
    rw [singular_subcomplex_inf_eq]
    congr 1
    ext x
    exact and_comm
  exact congrArg
    (supported_chain_complex (R := R)
      (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1))))
    hsub

end Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso
