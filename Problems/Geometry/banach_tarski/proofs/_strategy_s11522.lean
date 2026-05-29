import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

set_option maxHeartbeats 1000000 in
-- ρ^n applied to EuclideanSpace ℝ (Fin 3) blows past the default whnf budget; raise it.
-- hotel_subset_sphere: the orbit tower ⋃ₙ (ρ^n)''D of an origin-fixing isometry ρ stays
-- on S². Each (ρ^n) fixes 0 (induction, hfix) and an origin-fixing isometry preserves
-- norms (hnorm), so for d ∈ D ⊆ S² we get ‖(ρ^n) d‖ = ‖d‖ = 1. Sorry-free leaf.
theorem s11522 (D : Set E) (ρ : E ≃ᵢ E) (hρ0 : ρ 0 = 0)
    (hDs : D ⊆ Metric.sphere (0 : E) 1) :
    (⋃ n : ℕ, (ρ ^ n) '' D) ⊆ Metric.sphere (0 : E) 1  := by
  have hnorm : ∀ (g : E ≃ᵢ E), g 0 = 0 → ∀ z, ‖g z‖ = ‖z‖ := by
    intro g hg z
    calc ‖g z‖ = dist (g z) 0 := (dist_zero_right _).symm
      _ = dist (g z) (g 0) := by rw [hg]
      _ = dist z 0 := g.isometry.dist_eq z 0
      _ = ‖z‖ := dist_zero_right _
  have hfix : ∀ n : ℕ, (ρ ^ n) 0 = 0 := by
    intro n
    induction n with
    | zero => simp
    | succ k ih => rw [pow_succ]; change (ρ ^ k) (ρ 0) = 0; rw [hρ0, ih]
  intro x hx
  simp only [Set.mem_iUnion, Set.mem_image] at hx
  obtain ⟨n, d, hd, rfl⟩ := hx
  rw [Metric.mem_sphere, dist_zero_right, hnorm (ρ ^ n) (hfix n) d]
  have := hDs hd
  rw [Metric.mem_sphere, dist_zero_right] at this
  exact this

end Problems.Geometry.banach_tarski
