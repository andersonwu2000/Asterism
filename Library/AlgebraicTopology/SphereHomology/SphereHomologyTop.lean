import Mathlib
import Library.AlgebraicTopology.SphereHomology.CircleHomologyOne
import Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
import Library.AlgebraicTopology.SphereHomology.SphereSuspensionIso

open Library.AlgebraicTopology.SphereHomology.CircleHomologyOne
open Library.AlgebraicTopology.SphereHomology.HomotopyInvariance
open Library.AlgebraicTopology.SphereHomology.SphereSuspensionIso

namespace Library.AlgebraicTopology.SphereHomology.SphereHomologyTop

-- H_n(Sⁿ) ≅ R for n ≥ 1 by diagonal induction on n (data-producing `Nat.rec`, motive = an Iso).
-- Base (n=1): bridge the `TopCat.sphere 1 = ULift (Metric.sphere … Fin 2)` wrapper to the
-- non-ULift circle via `homotopy_equiv_singular_homology_iso (Homeomorph.ulift).toHomotopyEquiv`,
-- then `circle_homology_one_iso`. Step (n=k+1, k≥1): `sphere_suspension_homology_iso k k`
-- gives H_{k+1}(S^{k+1}) ≅ H_k(Sᵏ), closed by the induction hypothesis.
noncomputable def sphere_homology_top {R : Type} [Ring R] (n : ℕ) (hn : 1 ≤ n) :
    ((AlgebraicTopology.singularHomologyFunctor (ModuleCat.{0} R) n).obj
        (ModuleCat.of R R)).obj (TopCat.sphere n) ≅ ModuleCat.of R R  := by
  induction n with
  | zero => exact absurd hn (by omega)
  | succ k ih =>
    cases k with
    | zero =>
      exact homotopy_equiv_singular_homology_iso
          (Homeomorph.ulift (X := Metric.sphere (0 : EuclideanSpace ℝ (Fin 2)) 1)).toHomotopyEquiv 1
        ≪≫ circle_homology_one_iso
    | succ j =>
      exact sphere_suspension_homology_iso (j + 1) (j + 1) (by omega) ≪≫ ih (by omega)

end Library.AlgebraicTopology.SphereHomology.SphereHomologyTop
