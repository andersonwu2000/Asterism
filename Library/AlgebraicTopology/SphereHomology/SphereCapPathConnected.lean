import Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
import Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand

/-!
# Path-connectedness of spherical caps and bands

This file assembles the path-connectedness facts used to compute the reduced
homology of spheres via a Mayer-Vietoris cover. The two polar caps of a sphere
are contractible, hence path-connected, and the equatorial band between the
caps is homeomorphic to a product of a lower-dimensional sphere with an open
interval, hence also path-connected.

## Main statements

* `cap_path_connected`: the cap `{x : S^(n+2) | x_last ≠ -1}` is path-connected.
* `prod_path_connected`: a product of two path-connected spaces is path-connected.
* `band_path_connected`: the band `{x : S^(n+2) | x_last ≠ 1 ∧ x_last ≠ -1}` between
  the two poles is path-connected.
-/

open CategoryTheory CategoryTheory.Limits
open Library.AlgebraicTopology.SphereHomology.SphereConnectivityAndCaps
open Library.AlgebraicTopology.SphereHomology.SphereEquatorCylinderBand

namespace Library.AlgebraicTopology.SphereHomology.SphereCapPathConnected

/-- The cap `{x : S^(n+2) | x_last ≠ -1}` on the sphere `S^(n+2) ⊆ ℝ^(n+3)` is
path-connected: it is the sphere minus the south pole, which is contractible by
`pole_cap_contractible`, and every contractible space is path-connected. -/
theorem cap_path_connected (n : ℕ) :
    PathConnectedSpace
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
          x.1 (Fin.last (n + 2)) ≠ -1} := by
  haveI := pole_cap_contractible (n + 1) (-1) (Or.inr rfl)
  exact ContractibleSpace.instPathConnectedSpace

/-- The product of two path-connected spaces is path-connected: any two points
are joined componentwise using `Path.prod`. -/
theorem prod_path_connected {X Y : Type} [TopologicalSpace X] [TopologicalSpace Y]
    [PathConnectedSpace X] [PathConnectedSpace Y] : PathConnectedSpace (X × Y) := by
  refine ⟨inferInstance, fun p q => ?_⟩
  exact ⟨(PathConnectedSpace.joined p.1 q.1).somePath.prod
    (PathConnectedSpace.joined p.2 q.2).somePath⟩

/-- The equatorial band `{x : S^(n+2) | x_last ≠ 1 ∧ x_last ≠ -1}` is
path-connected: it is homeomorphic to the product of the sphere `S^(n+1)` with
the open interval `(-1, 1)`, both of which are path-connected. -/
theorem band_path_connected (n : ℕ) :
    PathConnectedSpace
      ↥{x : Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 3))) 1 |
          x.1 (Fin.last (n + 2)) ≠ 1 ∧ x.1 (Fin.last (n + 2)) ≠ -1} := by
  have hrank : 1 < Module.rank ℝ (EuclideanSpace ℝ (Fin (n + 2))) := by
    rw [← Module.finrank_eq_rank, finrank_euclideanSpace_fin]
    exact_mod_cast (show (1 : ℕ) < n + 2 by omega)
  haveI hS : PathConnectedSpace ↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1) :=
    isPathConnected_iff_pathConnectedSpace.mp (isPathConnected_sphere hrank 0 zero_le_one)
  haveI hI : PathConnectedSpace ↥(Set.Ioo (-1 : ℝ) 1) :=
    isPathConnected_iff_pathConnectedSpace.mp
      ((convex_Ioo (-1 : ℝ) 1).isPathConnected (Set.nonempty_Ioo.mpr (by norm_num)))
  haveI : PathConnectedSpace
      (↥(Metric.sphere (0 : EuclideanSpace ℝ (Fin (n + 2))) 1) × ↥(Set.Ioo (-1 : ℝ) 1)) :=
    prod_path_connected
  exact (band_homeo_sphere_prod_interval (n + 1)).symm.surjective.pathConnectedSpace
    (band_homeo_sphere_prod_interval (n + 1)).symm.continuous

end Library.AlgebraicTopology.SphereHomology.SphereCapPathConnected
