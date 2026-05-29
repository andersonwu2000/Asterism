import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- isometry_fixing_origin_maps_sphere: Isometry.dist_eq + origin-fixing ρ preserves S²
-- An isometry fixing the origin maps each sphere centred at 0 to itself,
-- since dist(ρ x, 0) = dist(ρ x, ρ 0) = dist(x, 0).
theorem isometry_fixing_origin_maps_sphere
    (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0)
    (x : E) (hx : x ∈ Metric.sphere (0 : E) 1) :
    ρ x ∈ Metric.sphere (0 : E) 1 := by
  simp only [Metric.mem_sphere] at hx ⊢
  calc dist (ρ x) 0 = dist (ρ x) (ρ 0) := by rw [hρ0]
    _ = dist x 0 := ρ.isometry.dist_eq x 0
    _ = 1 := hx

end Problems.Geometry.banach_tarski
