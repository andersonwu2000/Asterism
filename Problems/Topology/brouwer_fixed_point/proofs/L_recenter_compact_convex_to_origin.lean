import Mathlib
import Problems.Topology.brouwer_fixed_point.Defs

namespace Problems.Topology.brouwer_fixed_point

-- entry_kind: Builder
-- recenter_compact_convex_to_origin: translate S by -p so 0 lies in the interior
theorem recenter_compact_convex_to_origin
    {n : ℕ} {S : Set (EuclideanSpace ℝ (Fin n))} {p : EuclideanSpace ℝ (Fin n)}
    (hcomp : IsCompact S) (hconv : Convex ℝ S) (hp : p ∈ interior S) :
    ∃ T : Set (EuclideanSpace ℝ (Fin n)),
      IsCompact T ∧ Convex ℝ T ∧ (0 : EuclideanSpace ℝ (Fin n)) ∈ interior T ∧
        Nonempty (S ≃ₜ T) := by
  let e : EuclideanSpace ℝ (Fin n) ≃ₜ EuclideanSpace ℝ (Fin n) := Homeomorph.addRight (-p)
  refine ⟨e '' S, hcomp.image e.continuous, ?_, ?_, ⟨e.image S⟩⟩
  · -- Convexity: e is x ↦ x + (-p) = x - p, which preserves convexity
    intro x hx y hy a b ha hb hab
    obtain ⟨x', hx', rfl⟩ := hx
    obtain ⟨y', hy', rfl⟩ := hy
    refine ⟨a • x' + b • y', hconv hx' hy' ha hb hab, ?_⟩
    change a • x' + b • y' + -p = a • (x' + -p) + b • (y' + -p)
    simp only [smul_add, add_add_add_comm]
    congr 1
    rw [← add_smul, hab, one_smul]
  · -- 0 is in interior of e '' S
    apply e.isOpenMap.image_interior_subset
    exact ⟨p, hp, by simp [e, Homeomorph.addRight]⟩

end Problems.Topology.brouwer_fixed_point
