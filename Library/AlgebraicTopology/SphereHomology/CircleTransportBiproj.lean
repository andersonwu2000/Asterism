import Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
import Library.AlgebraicTopology.SphereHomology.SphereMVTransportBand
import Library.AlgebraicTopology.SphereHomology.SubspaceSupportedNaturality
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Transport of the circle Mayer–Vietoris `H₀` biproduct across supported subcomplexes

This file specializes the general Mayer–Vietoris transport machinery for supported
subcomplexes to the circle `S¹ ⊆ ℝ²`, covered by the two open arcs `U₊ = {x | x.last ≠ -1}`
and `U₋ = {x | x.last ≠ 1}`. It unwinds the biproduct decomposition of the `H₀` isomorphism
`circle_pair_h0_iso` along its `fst`/`snd` legs, and transports the `H₀`
intersection-inclusion naturality square across the bridge from the actual intersection
subcomplex `U₊ ⊓ U₋` to the "band" subcomplex model used elsewhere in the development.

## Main statements

* `circle_transport_fst_biproj`, `circle_transport_snd_biproj`: the `fst`/`snd` legs of
  `circle_pair_h0_iso` unwind to the `H₀`-maps induced by the inclusions of `U₊ ⊓ U₋` into
  `U₊` and `U₋` respectively (with a sign on the `snd` leg, matching the Mayer–Vietoris
  short complex map).
* `circle_inter_incl_a_h0_transport`, `inter_incl_b_h0_transport`: the naturality square for
  `subspace_supported_homology_iso` transports across the `⊓ → band` subcomplex bridge, on
  the `U₊` and `U₋` sides respectively.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.LongExactSequence
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
open Library.AlgebraicTopology.SphereHomology.SphereMVTransportBand
open Library.AlgebraicTopology.SphereHomology.SubspaceSupportedNaturality
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.CircleTransportBiproj

variable {R : Type} [Ring R]

/-- The `fst` (first-projection) leg of the circle Mayer–Vietoris `H₀` biproduct transport
square. Composing the `H₀`-map of `mv_short_complex` with `circle_pair_h0_iso.hom` and
projecting onto the first factor equals the `H₀`-map induced by the inclusion of `U₊ ⊓ U₋`
into `U₊` (where `U₊ = {x | x.last ≠ -1}` and `U₋ = {x | x.last ≠ 1}` are the two open arcs
covering the circle), transported along `subspace_supported_homology_iso` and
`TopCat.singularHomology₀ε`. -/
theorem circle_transport_fst_biproj :
    HomologicalComplex.homologyMap
        (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ 1})).f 0 ≫ (circle_pair_h0_iso (R := R)).hom
          ≫ ModuleCat.ofHom (LinearMap.fst R R R)
      = HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_left :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x | x.1 (Fin.last 1) ≠ -1}
                ⊓ singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x | x.1 (Fin.last 1) ≠ 1}
                ≤ singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x | x.1 (Fin.last 1) ≠ -1})) 0
        ≫ (subspace_supported_homology_iso (R := R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ -1} 0).hom
        ≫ TopCat.singularHomology₀ε
            (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
              x.1 (Fin.last 1) ≠ -1})) (ModuleCat.of R R)  := by
  have hproj :
      (circle_pair_h0_iso (R := R)).hom ≫ ModuleCat.ofHom (LinearMap.fst R R R)
        = (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) 0).map
              biprod.fst
          ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ -1} 0).hom
          ≫ TopCat.singularHomology₀ε
              (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ -1})) (ModuleCat.of R R) := by
    have hbp : (ModuleCat.biprodIsoProd (ModuleCat.of R R) (ModuleCat.of R R)).hom
          ≫ ModuleCat.ofHom (LinearMap.fst R R R) = biprod.fst := by
      rw [← ModuleCat.biprodIsoProd_inv_comp_fst (ModuleCat.of R R) (ModuleCat.of R R),
        Iso.hom_inv_id_assoc]
    unfold circle_pair_h0_iso mv_pair_homology_biprod_iso
    simp only [Iso.trans_hom, Functor.mapBiprod_hom, biprod.mapIso_hom, asIso_hom,
      Category.assoc, hbp, biprod.map_fst, biprod.map_fst_assoc]
    exact biprod.lift_fst_assoc _ _ _
  have hf :
      HomologicalComplex.homologyMap
          (mv_short_complex (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ -1})
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ 1})).f 0
        ≫ (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) 0).map
            biprod.fst
      = HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_left)) 0 := by
    change HomologicalComplex.homologyMap _ 0 ≫ HomologicalComplex.homologyMap biprod.fst 0 = _
    rw [← HomologicalComplex.homologyMap_comp]
    congr 1
    simp only [mv_short_complex, biprod.lift_fst]
  rw [hproj]
  simp only [← Category.assoc]
  exact congrArg
    (fun t => (t ≫ (subspace_supported_homology_iso (R := R)
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                {x | x.1 (Fin.last 1) ≠ -1} 0).hom)
              ≫ TopCat.singularHomology₀ε
                  (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1})) (ModuleCat.of R R)) hf

/-- The circle (`Fin 2`-ambient) analogue of the `H₀` intersection-inclusion naturality
transport on the `U₊` side. The naturality square for `subspace_supported_homology_iso`
along the inclusion `{x | x.last ≠ 1 ∧ x.last ≠ -1} ⊆ U₊` transports, via the propositional
equality between the intersection subcomplex `U₊ ⊓ U₋` and the "band" subcomplex model
(`singular_subcomplex_inf_eq` together with `and_comm`), across the bridge isomorphism
`inter_supported_homology_iso_band`. -/
theorem circle_inter_incl_a_h0_transport
    (h : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} ⊆
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ -1}) :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_left :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1} ⊓
                singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ 1} ≤
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1})) 0
        ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ -1} 0).hom
      = (inter_supported_homology_iso_band (R := R) 0 0).hom
        ≫ ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
              (ModuleCat.of R R)).map
              (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)  := by
  have hsub :
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ -1} ⊓
        singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ 1} =
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} := by
    rw [singular_subcomplex_inf_eq]
    congr 1
    ext x
    exact and_comm
  have hle_band :
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} ≤
        singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ -1} :=
    hsub ▸ inf_le_left
  have hnat := subspace_supported_homology_iso_naturality (R := R)
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)) h 0 hle_band
  have e :
      (supported_chain_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ -1} ⊓
            singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1})).homology 0
        = (supported_chain_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1})).homology 0 :=
    congrArg (fun s => (supported_chain_complex (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            s).homology 0) hsub
  have hA :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_left :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1} ⊓
                singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ 1} ≤
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1})) 0
        = eqToHom e ≫ HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R)
              (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
                hle_band) 0 :=
    supported_chain_incl_congr_left (R := R)
      (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
      hsub inf_le_left hle_band 0
  have hC :
      (inter_supported_homology_iso_band (R := R) 0 0).hom
        = eqToHom e ≫ (subspace_supported_homology_iso (R := R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
              x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} 0).hom := by
    change (inter_supported_homology_iso_band (R := R) 0 0).hom = _
    unfold inter_supported_homology_iso_band
    rw [Iso.trans_hom]
    congr 1
  rw [hA, hC]
  simp only [Category.assoc]
  rw [hnat]
  exact (Category.assoc _ _ _).symm

/-- The `U₋` mirror of `circle_inter_incl_a_h0_transport`: the naturality square for
`subspace_supported_homology_iso` along the inclusion `{x | x.last ≠ 1 ∧ x.last ≠ -1} ⊆ U₋`
transports across the bridge from the intersection subcomplex `U₊ ⊓ U₋` to the "band"
subcomplex model. -/
theorem inter_incl_b_h0_transport
    (h : {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} ⊆
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ 1}) :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_right :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1} ⊓
                singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ 1} ≤
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ 1})) 0
        ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1} 0).hom
      = (inter_supported_homology_iso_band (R := R) 0 0).hom
        ≫ ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 0).obj
              (ModuleCat.of R R)).map
              (TopCat.ofHom ⟨Set.inclusion h, continuous_inclusion h⟩)  := by
  have hsub :
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ -1} ⊓
        singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ 1} =
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} := by
    rw [singular_subcomplex_inf_eq]
    congr 1
    ext x
    exact and_comm
  have hle_band :
      singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} ≤
        singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
          {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ 1} :=
    hsub ▸ inf_le_right
  have hnat := subspace_supported_homology_iso_naturality (R := R)
      (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)) h 0 hle_band
  have e :
      (supported_chain_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 | x.1 (Fin.last 1) ≠ -1} ⊓
            singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1})).homology 0
        = (supported_chain_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1})).homology 0 :=
    congrArg (fun s => (supported_chain_complex (R := R)
        (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            s).homology 0) hsub
  have hA :
      HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_right :
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ -1} ⊓
                singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ 1} ≤
              singular_subcomplex_of_set
                  (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                  {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                    x.1 (Fin.last 1) ≠ 1})) 0
        = eqToHom e ≫ HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R)
              (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
                hle_band) 0 :=
    supported_chain_incl_congr_left (R := R)
      (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
      hsub inf_le_right hle_band 0
  have hC :
      (inter_supported_homology_iso_band (R := R) 0 0).hom
        = eqToHom e ≫ (subspace_supported_homology_iso (R := R)
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
              x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} 0).hom := by
    change (inter_supported_homology_iso_band (R := R) 0 0).hom = _
    unfold inter_supported_homology_iso_band
    rw [Iso.trans_hom]
    congr 1
  rw [hA, hC]
  simp only [Category.assoc]
  rw [hnat]
  exact (Category.assoc _ _ _).symm

/-- The `snd` (second-projection) leg of the circle Mayer–Vietoris `H₀` biproduct transport
square, mirroring `circle_transport_fst_biproj`. Composing with `circle_pair_h0_iso.hom` and
projecting onto the second factor equals minus the `H₀`-map induced by the inclusion of
`U₊ ⊓ U₋` into `U₋`, the sign coming from the `snd` leg of the Mayer–Vietoris short complex
map. -/
theorem circle_transport_snd_biproj :
    HomologicalComplex.homologyMap
        (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ 1})).f 0 ≫ (circle_pair_h0_iso (R := R)).hom
          ≫ ModuleCat.ofHom (LinearMap.snd R R R)
      = - (HomologicalComplex.homologyMap
            (supported_chain_complex_incl (R := R)
              (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
              (inf_le_right :
                singular_subcomplex_of_set
                    (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                    {x | x.1 (Fin.last 1) ≠ -1}
                  ⊓ singular_subcomplex_of_set
                    (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                    {x | x.1 (Fin.last 1) ≠ 1}
                  ≤ singular_subcomplex_of_set
                    (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                    {x | x.1 (Fin.last 1) ≠ 1})) 0
          ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ 1} 0).hom
          ≫ TopCat.singularHomology₀ε
              (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R))  := by
  have hproj :
      (circle_pair_h0_iso (R := R)).hom ≫ ModuleCat.ofHom (LinearMap.snd R R R)
        = (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) 0).map
              biprod.snd
          ≫ (subspace_supported_homology_iso (R := R)
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ 1} 0).hom
          ≫ TopCat.singularHomology₀ε
              (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
                x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R) := by
    have hbp : (ModuleCat.biprodIsoProd (ModuleCat.of R R) (ModuleCat.of R R)).hom
          ≫ ModuleCat.ofHom (LinearMap.snd R R R) = biprod.snd := by
      rw [← ModuleCat.biprodIsoProd_inv_comp_snd (ModuleCat.of R R) (ModuleCat.of R R),
        Iso.hom_inv_id_assoc]
    unfold circle_pair_h0_iso mv_pair_homology_biprod_iso
    simp only [Iso.trans_hom, Functor.mapBiprod_hom, biprod.mapIso_hom, asIso_hom,
      Category.assoc, hbp, biprod.map_snd, biprod.map_snd_assoc]
    exact biprod.lift_snd_assoc _ _ _
  have hf :
      HomologicalComplex.homologyMap
          (mv_short_complex (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ -1})
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ 1})).f 0
        ≫ (HomologicalComplex.homologyFunctor (ModuleCat.{0} R) (ComplexShape.down ℕ) 0).map
            biprod.snd
      = - HomologicalComplex.homologyMap
          (supported_chain_complex_incl (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (inf_le_right)) 0 := by
    change HomologicalComplex.homologyMap _ 0 ≫ HomologicalComplex.homologyMap biprod.snd 0 = _
    rw [← HomologicalComplex.homologyMap_comp, ← HomologicalComplex.homologyMap_neg]
    congr 1
    simp only [mv_short_complex, biprod.lift_snd]
  rw [hproj]
  have hcomb := congrArg
    (fun t => t ≫ ((subspace_supported_homology_iso (R := R)
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
        {x | x.1 (Fin.last 1) ≠ 1} 0).hom
      ≫ TopCat.singularHomology₀ε
          (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R))) hf
  exact hcomb.trans (Preadditive.neg_comp _ _)

end Library.AlgebraicTopology.SphereHomology.CircleTransportBiproj
