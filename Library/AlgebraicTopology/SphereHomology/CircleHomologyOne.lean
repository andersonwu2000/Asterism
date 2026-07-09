import Mathlib
import Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
import Library.AlgebraicTopology.SphereHomology.CircleMVKernelTransport
import Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
import Library.AlgebraicTopology.SphereHomology.CircleTransportGeom
import Library.AlgebraicTopology.SphereHomology.SphereMVConnectingMap
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso
import Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
import Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.SphereHomology.CircleMVAugmentation
open Library.AlgebraicTopology.SphereHomology.CircleMVKernelTransport
open Library.AlgebraicTopology.SphereHomology.CirclePairH0Iso
open Library.AlgebraicTopology.SphereHomology.CircleTransportGeom
open Library.AlgebraicTopology.SphereHomology.SphereMVConnectingMap
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso
open Library.AlgebraicTopology.SphereHomology.SphereZeroDimHomology
open Library.AlgebraicTopology.SphereHomology.SupportedSubcomplexHomologyIso

namespace Library.AlgebraicTopology.SphereHomology.CircleHomologyOne

-- circle_homology_one_iso: H₁(S¹) ≅ R via kernel.mapIso transport of the MV connecting-kernel
-- iso onto the concrete augmentation-doubling map's kernel.
-- The previous attempt cited `circle_mv_kernel_iso`, whose chain
-- (circle_mv_kernel_iso -> circle_mv_kernel_transport -> circle_mv_h0_transport_square)
-- bottoms out in a `sorry` stub (`circle_mv_h0_transport_square` is `:= by sorry` on disk,
-- despite the standing directive's claim it was proved) -- lake build correctly rejected the
-- transitive sorryAx. This version bypasses that broken alias by inlining the same
-- kernel.mapIso step directly from the already sorry-free `circle_transport_comm_explicit`
-- (which supplies the p/q vertical isos and the commuting square in one shot, assembled from
-- its own landed `circle_transport_fst`/`circle_transport_snd` sub-bricks), then composing with
-- `circle_mv_augmentation_kernel` (kernel of the augmentation map ≅ R) and
-- `mv_connecting_kernel_iso` (H₁(S¹) ≅ kernel of the MV map at n = 0).
noncomputable def circle_homology_one_iso {R : Type} [Ring R] :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) 1).obj
          (ModuleCat.of R R)).obj
        (TopCat.of (Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)) ≅
      ModuleCat.of R R := by
  obtain ⟨hA, hB, hAB⟩ := sphere_cover_open_union 0
  exact mv_connecting_kernel_iso hA hB hAB 0 (mv_pair_homology_zero 0 1 le_rfl) ≪≫
    kernel.mapIso _ _
      (inter_supported_homology_iso_band (R := R) 0 0
        ≪≫ band_singular_homology_iso_lower_sphere (R := R) 0 0
        ≪≫ sphere_zero_h0_iso (R := R))
      (circle_pair_h0_iso (R := R))
      (circle_transport_comm_explicit (R := R)) ≪≫
    circle_mv_augmentation_kernel

end Library.AlgebraicTopology.SphereHomology.CircleHomologyOne
