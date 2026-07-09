import Mathlib
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
import Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso

open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SphereMVDeltaSetup
open Library.AlgebraicTopology.SphereHomology.SphereMVPairAndDeltaIso

namespace Library.AlgebraicTopology.SphereHomology.SphereSuspensionIso

-- Suspension iso for sphere homology: strip the ULift wrapper on each side
-- (Homeomorph.ulift → homotopy equiv → homology iso), apply the MV boundary iso
-- H_{k+1}(Sⁿ⁺¹)≅H_k(band) and the band dimension-drop H_k(band)≅H_k(Sⁿ).
noncomputable def sphere_suspension_homology_iso {R : Type} [Ring R] (n k : ℕ) (hk : 1 ≤ k) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) (k+1)).obj
        (ModuleCat.of R R)).obj (TopCat.sphere (n+1)) ≅
      ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) k).obj
        (ModuleCat.of R R)).obj (TopCat.sphere n)  := by
  have eu2 := Homeomorph.ulift (X := Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+2))) 1)
  have eu1 := Homeomorph.ulift (X := Metric.sphere (0 : EuclideanSpace ℝ (Fin (n+1))) 1)
  exact
    homotopy_equiv_singular_homology_iso eu2.toHomotopyEquiv (k+1)
      ≪≫ sphere_mv_delta_iso n k hk
      ≪≫ band_singular_homology_iso_lower_sphere n k
      ≪≫ (homotopy_equiv_singular_homology_iso eu1.toHomotopyEquiv k).symm

end Library.AlgebraicTopology.SphereHomology.SphereSuspensionIso
