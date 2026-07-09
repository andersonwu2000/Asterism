import Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
import Library.AlgebraicTopology.SphereHomology.SphereCapPathConnected
import Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
import Library.AlgebraicTopology.SphereHomology.SphereMVTransportBand
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Mono facts for singular $H_0$ of sphere covers

This file assembles the point-set and homological inputs needed to show that the
inclusion-induced maps on singular $H_0$ arising from the standard open cover of a sphere
by an "upper cap" and a "lower cap" are monomorphisms. These are exactly the hypotheses fed
into the Mayer–Vietoris long exact sequence computation of the sphere's homology.

## Main statements

* `band_cap_singular_h0_mono`: the singular $H_0$ map induced by the inclusion of the
  "band" `{x | x.1 (Fin.last (n+2)) ≠ 1 ∧ x.1 (Fin.last (n+2)) ≠ -1}` into the "upper cap"
  `{x | x.1 (Fin.last (n+2)) ≠ -1}` is mono, since both spaces are path-connected.
* `inter_incl_a_h0_mono`: the homology map induced by the inclusion of supported chain
  complexes `A ⊓ B ≤ A` is mono at degree `0`, transported along the naturality square
  relating supported-subcomplex homology and singular homology.
* `inter_incl_h0_mono`: the Mayer–Vietoris short complex map `.f` is mono at $H_0$,
  obtained by factoring through the first biproduct projection and citing
  `inter_incl_a_h0_mono`.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.LongExactSequence
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
open Library.AlgebraicTopology.SphereHomology.SphereCapPathConnected
open Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
open Library.AlgebraicTopology.SphereHomology.SphereMVTransportBand
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.SphereH0MonoFacts

variable {R : Type} [Ring R] (n : ℕ)

/-- The singular $H_0$ map induced by the topological inclusion of the band
`{x | x.1 (Fin.last (n+2)) ≠ 1 ∧ x.1 (Fin.last (n+2)) ≠ -1}` into the upper cap
`{x | x.1 (Fin.last (n+2)) ≠ -1}` is a monomorphism. Both the band and the cap are
path-connected subspaces of the sphere, so this reduces to the abstract fact
`singular_h0_map_mono_of_path_connected`: for any map between path-connected spaces, the
induced singular-$H_0$ map is (an isomorphism, hence) mono, via the augmentation
`TopCat.singularHomology₀ε` being an isomorphism on both ends together with its
naturality. -/
theorem band_cap_singular_h0_mono
    (h : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ 1 ∧ x.1 (Fin.last (n+2)) ≠ -1} ⊆
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1}) :
    CategoryTheory.Mono
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
          (ModuleCat.of R R)).map
        (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)) := by
  have hband := band_path_connected n
  have hcap := cap_path_connected n
  exact singular_h0_map_mono_of_path_connected hband hcap _

/-- The homology map induced by the inclusion of supported chain complexes `A ⊓ B ≤ A` is
mono at degree `0`. This transports `band_cap_singular_h0_mono` along the naturality square
relating the supported-subcomplex homology isomorphism to singular homology
(`inter_supported_homology_iso_band_naturality`). -/
theorem inter_incl_a_h0_mono
    (_hA : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ -1})
    (_hB : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1})
    (_hAB : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1} ∪
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ 1} = Set.univ) :
    CategoryTheory.Mono
      (HomologicalComplex.homologyMap
        (supported_chain_complex_incl (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
          (inf_le_left :
            singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
                {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                  x.1 (Fin.last (n+2)) ≠ -1} ⊓
              singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
                {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                  x.1 (Fin.last (n+2)) ≠ 1} ≤
            singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
                {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                  x.1 (Fin.last (n+2)) ≠ -1})) 0) := by
  have h : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1 ∧ x.1 (Fin.last (n+2)) ≠ -1} ⊆
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 | x.1 (Fin.last (n+2)) ≠ -1} :=
    fun x hx => hx.2
  have hg : CategoryTheory.Mono
      (((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
          (ModuleCat.of R R)).map
        (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)) :=
    band_cap_singular_h0_mono n h
  have hsq :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)))
            (inf_le_left :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                    x.1 (Fin.last (n+2)) ≠ -1} ⊓
                singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                    x.1 (Fin.last (n+2)) ≠ 1} ≤
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                    x.1 (Fin.last (n+2)) ≠ -1})) 0
        ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
                x.1 (Fin.last (n+2)) ≠ -1} 0).hom
      = (inter_supported_homology_iso_band (R := R) (n+1) 0).hom
        ≫ ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
              (ModuleCat.of R R)).map
            (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩) :=
    inter_supported_homology_iso_band_naturality n h
  rw [← mono_comp_iff_of_mono _ (subspace_supported_homology_iso (R := R)
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1} 0).hom, hsq]
  exact (mono_comp_iff_of_isIso _ _).mpr hg

/-- The Mayer–Vietoris short complex map `.f` is mono at $H_0$. Since
`(mv_short_complex X A B).f = biprod.lift (inclA) (-inclB)`, composing with the first
biproduct projection recovers the inclusion `A ⊓ B ≤ A` (`biprod.lift_fst`); applying the
homology functor and citing `inter_incl_a_h0_mono` for the resulting mono factors through
`mono_of_mono_fac`. -/
theorem inter_incl_h0_mono
    (hA : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ -1})
    (hB : IsOpen {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
        x.1 (Fin.last (n+2)) ≠ 1})
    (hAB : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ -1} ∪
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 |
          x.1 (Fin.last (n+2)) ≠ 1} = Set.univ) :
    CategoryTheory.Mono
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
              x.1 (Fin.last (n+2)) ≠ 1})).f 0) := by
  set X : SSet :=
    TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1)) with hXdef
  set A : X.Subcomplex := singular_subcomplex_of_set
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 | x.1 (Fin.last (n+2)) ≠ -1}
      with hAdef
  set B : X.Subcomplex := singular_subcomplex_of_set
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1))
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+3))) 1 | x.1 (Fin.last (n+2)) ≠ 1}
      with hBdef
  have hmono : Mono (HomologicalComplex.homologyMap
      (supported_chain_complex_incl (R := R) X (inf_le_left : A ⊓ B ≤ A)) 0) :=
    inter_incl_a_h0_mono (R := R) n hA hB hAB
  have hcomp : (mv_short_complex (R := R) X A B).f ≫
        (biprod.fst : _ ⟶ supported_chain_complex (R := R) X A) =
      supported_chain_complex_incl (R := R) X (inf_le_left : A ⊓ B ≤ A) :=
    biprod.lift_fst _ _
  have hfac : HomologicalComplex.homologyMap (mv_short_complex (R := R) X A B).f 0 ≫
      HomologicalComplex.homologyMap
        (biprod.fst : _ ⟶ supported_chain_complex (R := R) X A) 0 =
      HomologicalComplex.homologyMap
        (supported_chain_complex_incl (R := R) X (inf_le_left : A ⊓ B ≤ A)) 0 := by
    have h := HomologicalComplex.homologyMap_comp (mv_short_complex (R := R) X A B).f
      (biprod.fst : _ ⟶ supported_chain_complex (R := R) X A) 0
    rw [hcomp] at h
    exact h.symm
  exact @mono_of_mono_fac _ _ _ _ _ _ _ _ hmono hfac

end Library.AlgebraicTopology.SphereHomology.SphereH0MonoFacts
