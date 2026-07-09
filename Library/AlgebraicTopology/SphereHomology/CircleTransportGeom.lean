import Library.AlgebraicTopology.SphereHomology.CircleBandAugmentation
import Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
import Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
import Library.AlgebraicTopology.SphereHomology.CircleTransportBiproj
import Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

/-!
# Geometric transport squares for the circle Mayer–Vietoris `H₀` computation

This file finishes the verification that the categorical transport square arising from the
biproduct decomposition of `circle_pair_h0_iso` agrees, component by component, with the
geometric augmentation map `circle_mv_augmentation_map` computed from the two contractible
half-circle covers `U⁺ = {x | x_last ≠ -1}` and `U⁻ = {x | x_last ≠ 1}` of `S¹`.

## Main statements

* `circle_transport_fst_geom`, `circle_transport_snd_geom`: the geometric legs of the
  transport square, identifying each inclusion-induced `H₀` map with the corresponding
  projection of `circle_mv_augmentation_map`.
* `circle_transport_fst`, `circle_transport_snd`: the transport square split along the
  `fst`/`snd` projections of `R × R`, obtained by combining the purely categorical biproduct
  unwinding (`circle_transport_fst_biproj`, `circle_transport_snd_biproj`) with the geometric
  legs above.
* `circle_transport_comm_explicit`: the full (unsplit) transport square, reassembled from its
  two projections via `Prod.ext`.

## Implementation notes

Throughout, `R` ranges over an arbitrary ring, and `S¹` is realized as
`Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1`.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.CircleBandAugmentation
open Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
open Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
open Library.AlgebraicTopology.SphereHomology.CircleTransportBiproj
open Library.AlgebraicTopology.SphereHomology.SingularH0Naturality
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.CircleTransportGeom

variable {R : Type} [Ring R]

/-- The geometric leg of the `fst`-projected circle Mayer–Vietoris `H₀` transport square, on
the `U⁺ = {x | x_last ≠ -1}` side: the inclusion-induced homology map
`H₀(A ⊓ B ↪ U⁺) ≫ subspace_supported_homology_iso.hom ≫ singularHomology₀ε` equals
`Φ.hom ≫ circle_mv_augmentation_map ≫ fst`, since both band arcs land in the contractible
cap `U⁺` and sum. -/
theorem circle_transport_fst_geom :
      HomologicalComplex.homologyMap
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
              x.1 (Fin.last 1) ≠ -1})) (ModuleCat.of R R)
      = (inter_supported_homology_iso_band (R := R) 0 0
          ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
          ≪≫ sphere_zero_h0_iso (R := R)).hom
        ≫ circle_mv_augmentation_map (R := R)
        ≫ ModuleCat.ofHom (LinearMap.fst R R R) := by
  have hsub :
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} ⊆
      {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ -1} := fun x hx => hx.2
  refine Eq.trans
    ((circle_inter_incl_a_h0_transport (R := R) hsub) =≫
      TopCat.singularHomology₀ε
        (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
          x.1 (Fin.last 1) ≠ -1})) (ModuleCat.of R R)) ?_
  refine Eq.trans
    ((inter_supported_homology_iso_band (R := R) 0 0).hom ≫=
      singular_h0_augmentation_naturality
        (TopCat.ofHom ⟨Set.inclusion hsub, continuous_inclusion hsub⟩)) ?_
  rw [band_aug_coord_sum, circle_mv_augmentation_map]
  simp only [Iso.trans_hom, Category.assoc, ← ModuleCat.ofHom_comp, LinearMap.fst_prod]

/-- Split the `fst`-projected circle Mayer–Vietoris `H₀` transport square into a pure
categorical step and a geometric one. `circle_transport_fst_biproj` unwinds the biproduct:
the left-hand side `f 0 ≫ circle_pair_h0_iso.hom ≫ fst` collapses (via `biprod.lift_fst`,
`biprod.map_fst`, `Functor.mapBiprod`, `ModuleCat.biprodIsoProd`) to the `U⁺`-inclusion
homology map `homologyMap (incl (A ⊓ B ≤ A)) 0 ≫ subspace_supported_homology_iso.hom ≫
singularHomology₀ε`. `circle_transport_fst_geom` supplies the remaining geometry: that
inclusion-induced `H₀` map equals `Φ.hom ≫ circle_mv_augmentation_map ≫ fst`. -/
theorem circle_transport_fst :
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
      = (inter_supported_homology_iso_band (R := R) 0 0
          ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
          ≪≫ sphere_zero_h0_iso (R := R)).hom
        ≫ circle_mv_augmentation_map (R := R)
        ≫ ModuleCat.ofHom (LinearMap.fst R R R) :=
  (circle_transport_fst_biproj (R := R)).trans (circle_transport_fst_geom (R := R))

/-- Geometric leg of the `snd`-projected circle Mayer–Vietoris `H₀` transport square, on the
`U⁻ = {x | x_last ≠ 1}` side. Mirrors `circle_transport_fst_geom`, with the leading minus
sign of the `snd` biproduct leg: `inter_incl_b_h0_transport` rewrites
`homologyMap incl ≫ iso.hom` as `band-iso ≫ H(band ↪ U⁻)`;
`singular_h0_augmentation_naturality` collapses `H(band ↪ U⁻) ≫ ε_{U⁻}` to `ε_band`;
`band_aug_coord_sum` computes `ε_band` as the `S⁰` coordinate sum `fst + snd`. The `snd`
projection of `circle_mv_augmentation_map` is `-(fst + snd)`, matching the negation on the
left-hand side. -/
theorem circle_transport_snd_geom :
      - (HomologicalComplex.homologyMap
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
                x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R))
      = (inter_supported_homology_iso_band (R := R) 0 0
          ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
          ≪≫ sphere_zero_h0_iso (R := R)).hom
        ≫ circle_mv_augmentation_map (R := R)
        ≫ ModuleCat.ofHom (LinearMap.snd R R R) := by
  have hinner :
      HomologicalComplex.homologyMap
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
              x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R)
      = (inter_supported_homology_iso_band (R := R) 0 0
          ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
          ≪≫ sphere_zero_h0_iso (R := R)).hom
        ≫ ModuleCat.ofHom (LinearMap.fst R R R + LinearMap.snd R R R) := by
    have hsub :
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1 ∧ x.1 (Fin.last 1) ≠ -1} ⊆
        {x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1} := fun x hx => hx.1
    refine Eq.trans
      ((inter_incl_b_h0_transport (R := R) hsub) =≫
        TopCat.singularHomology₀ε
          (TopCat.of ↥({x : Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1 |
            x.1 (Fin.last 1) ≠ 1})) (ModuleCat.of R R)) ?_
    refine Eq.trans
      ((inter_supported_homology_iso_band (R := R) 0 0).hom ≫=
        singular_h0_augmentation_naturality
          (TopCat.ofHom ⟨Set.inclusion hsub, continuous_inclusion hsub⟩)) ?_
    rw [band_aug_coord_sum]
    simp only [Iso.trans_hom, Category.assoc]
  rw [hinner, circle_mv_augmentation_map]
  simp only [← ModuleCat.ofHom_comp, LinearMap.snd_prod]
  exact (Preadditive.comp_neg _ _).symm

/-- Mirror of `circle_transport_fst`, projected onto the `snd` factor of the circle
Mayer–Vietoris `H₀` transport square (the `U⁻` side). `circle_transport_snd_biproj` unwinds
the biproduct: `f 0 ≫ circle_pair_h0_iso.hom ≫ snd` collapses to the negated `U⁻`-inclusion
homology composite, the minus being the `-(incl A ⊓ B → B)` leg of `biprod.lift`.
`circle_transport_snd_geom` supplies the matching geometry, `Φ.hom ≫
circle_mv_augmentation_map ≫ snd`, and the two legs compose via `Eq.trans`. -/
theorem circle_transport_snd :
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
      = (inter_supported_homology_iso_band (R := R) 0 0
          ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
          ≪≫ sphere_zero_h0_iso (R := R)).hom
        ≫ circle_mv_augmentation_map (R := R)
        ≫ ModuleCat.ofHom (LinearMap.snd R R R) := by
  exact (circle_transport_snd_biproj (R := R)).trans (circle_transport_snd_geom (R := R))

/-- The full (unsplit) circle Mayer–Vietoris `H₀` transport square: `H₀` of the canonical map
out of the intersection complex, followed by `circle_pair_h0_iso.hom`, agrees with the
geometric composite through `circle_mv_augmentation_map`. Proved by splitting the target
`R × R` into its two scalar components via `LinearMap.fst`/`LinearMap.snd`
(`circle_transport_fst`, `circle_transport_snd`) and reassembling with `Prod.ext`. -/
theorem circle_transport_comm_explicit :
    HomologicalComplex.homologyMap
        (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ 1})).f 0 ≫ (circle_pair_h0_iso (R := R)).hom
      = (inter_supported_homology_iso_band (R := R) 0 0
          ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
          ≪≫ sphere_zero_h0_iso (R := R)).hom
        ≫ circle_mv_augmentation_map (R := R) := by
  have hfst :
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
        = (inter_supported_homology_iso_band (R := R) 0 0
            ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
            ≪≫ sphere_zero_h0_iso (R := R)).hom
          ≫ circle_mv_augmentation_map (R := R)
          ≫ ModuleCat.ofHom (LinearMap.fst R R R) := circle_transport_fst (R := R)
  have hsnd :
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
        = (inter_supported_homology_iso_band (R := R) 0 0
            ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
            ≪≫ sphere_zero_h0_iso (R := R)).hom
          ≫ circle_mv_augmentation_map (R := R)
          ≫ ModuleCat.ofHom (LinearMap.snd R R R) := circle_transport_snd (R := R)
  apply ModuleCat.hom_ext
  apply LinearMap.ext
  intro x
  apply Prod.ext
  · have h := congrArg (fun m : _ ⟶ ModuleCat.of R R => m.hom x) hfst
    simpa using h
  · have h := congrArg (fun m : _ ⟶ ModuleCat.of R R => m.hom x) hsnd
    simpa using h

end Library.AlgebraicTopology.SphereHomology.CircleTransportGeom
