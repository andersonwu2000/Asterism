import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- conjugate_orbit_norm_bound: ‖c - Rⁿc‖ ≤ 2‖c‖ ≤ 1 via triangle ineq + isometry norm
theorem conjugate_orbit_norm_bound (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hc : ‖c‖ ≤ 1 / 2) (n : ℕ) :
    ‖c - (R ^ n) c‖ ≤ 1 := by
  calc ‖c - (R ^ n) c‖
      ≤ ‖c‖ + ‖(R ^ n) c‖ := norm_sub_le _ _
    _ = ‖c‖ + ‖c‖ := by rw [(R ^ n).norm_map]
    _ ≤ 1 := by linarith

end Problems.Geometry.banach_tarski
