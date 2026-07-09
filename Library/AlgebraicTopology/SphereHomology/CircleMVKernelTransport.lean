import Mathlib
import Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
import Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
import Library.AlgebraicTopology.SphereHomology.CircleTransportGeom
import Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.MayerVietoris.ShortExactComplex
open Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
open Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
open Library.AlgebraicTopology.SphereHomology.CircleTransportGeom
open Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.CircleMVKernelTransport

-- Assemble the transport-square witness (p, q, w) for `circle_mv_kernel_transport`.
-- p = intersection (band) H₀ iso, spelled INLINE (never a named decl — dedup lesson):
--     inter_supported_homology_iso_band ≪≫ band_singular_… ≪≫ sphere_zero_h0_iso.
-- q = circle_pair_h0_iso (total pair H₀ iso, landed).
-- w = commutativity homologyMap …f 0 ≫ q.hom = p.hom ≫ aug, supplied by the
--     open sibling `circle_transport_comm_explicit` (auto-linked; waits on its proof).
noncomputable def circle_mv_h0_transport_square {R : Type} [Ring R] :
    Σ' (p : (mv_short_complex (R := R)
              (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
              (singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                {x | x.1 (Fin.last 1) ≠ -1})
              (singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                {x | x.1 (Fin.last 1) ≠ 1})).X₁.homology 0 ≅ ModuleCat.of R (R × R))
       (q : (mv_short_complex (R := R)
              (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
              (singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                {x | x.1 (Fin.last 1) ≠ -1})
              (singular_subcomplex_of_set
                (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
                {x | x.1 (Fin.last 1) ≠ 1})).X₂.homology 0 ≅ ModuleCat.of R (R × R)),
      HomologicalComplex.homologyMap
          (mv_short_complex (R := R)
            (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ -1})
            (singular_subcomplex_of_set
              (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
              {x | x.1 (Fin.last 1) ≠ 1})).f 0 ≫ q.hom
        = p.hom ≫ circle_mv_augmentation_map (R := R)  :=
  ⟨inter_supported_homology_iso_band (R := R) 0 0
      ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
      ≪≫ sphere_zero_h0_iso (R := R),
    circle_pair_h0_iso (R := R),
    circle_transport_comm_explicit (R := R)⟩

-- kernel.mapIso over the transported MV square.
-- Sub-goal `circle_mv_h0_transport_square` supplies (p, q, w): vertical isos
-- p : X₁.homology 0 ≅ R×R, q : X₂.homology 0 ≅ R×R and the commutativity
-- w : homologyMap …f 0 ≫ q.hom = p.hom ≫ aug (dedup-links to / revives the shelved
-- `circle_mv_transport_square` twin — same statement).
-- `kernel.mapIso _ _ p q w` then transports kernel(MV map at H₀) ≅ kernel(augmentation map).

noncomputable def circle_mv_kernel_transport {R : Type} [Ring R] :
    CategoryTheory.Limits.kernel
      (HomologicalComplex.homologyMap
        (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ 1})).f 0) ≅
      CategoryTheory.Limits.kernel (circle_mv_augmentation_map (R := R)) := by
  obtain ⟨p, q, w⟩ := circle_mv_h0_transport_square (R := R)
  exact kernel.mapIso _ _ p q w

-- Decompose kernel(MV map at H₀) ≅ R for S¹ into: (1) `circle_mv_kernel_transport`,
-- transporting the opaque MV homology map onto the explicit augmentation-doubling map
-- `circle_mv_augmentation_map : (a,b) ↦ (a+b, -(a+b))` on R×R (via the landed dictionary
-- + naturality bricks, a kernel.mapIso of the transported squares); then (2)
-- `circle_mv_augmentation_kernel`, the concrete linear-algebra kernel ≅ R (antidiagonal
-- {(a,-a)}).  The two isos share the middle object `kernel circle_mv_augmentation_map`, so
-- the parent is their `Iso.trans`.
noncomputable def circle_mv_kernel_iso {R : Type} [Ring R] :
    CategoryTheory.Limits.kernel
      (HomologicalComplex.homologyMap
        (mv_short_complex (R := R)
          (TopCat.toSSet.obj (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)))
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ -1})
          (singular_subcomplex_of_set
            (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1))
            {x | x.1 (Fin.last 1) ≠ 1})).f 0) ≅
      ModuleCat.of R R  :=
  circle_mv_kernel_transport ≪≫ circle_mv_augmentation_kernel

end Library.AlgebraicTopology.SphereHomology.CircleMVKernelTransport
