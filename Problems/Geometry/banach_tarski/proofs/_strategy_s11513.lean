import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_conjugate_orbit_formula
import Problems.Geometry.banach_tarski.proofs.L_conjugate_orbit_ne_zero
import Problems.Geometry.banach_tarski.proofs.L_conjugate_orbit_norm_bound
import Problems.Geometry.banach_tarski.proofs.L_exists_conjugated_isometry

namespace Problems.Geometry.banach_tarski

-- Conjugate a small-vector linear rotation `R` by the translation `x ↦ x - c`:
-- `ρ x = R (x - c) + c` is an isometry whose origin-orbit satisfies `(ρ ^ n) 0 = c - R ^ n c`.
-- Sub-goals: (1) build the conjugated isometry with that pointwise formula;
-- (2) the closed-form orbit by induction; (3) the orbit lies in the unit ball
-- (`‖c - R ^ n c‖ ≤ 2‖c‖ ≤ 1`); (4) it never returns to `0` for `n ≥ 1` (from `hfix`).
theorem s11513 (R : E ≃ₗᵢ[ℝ] E) (c : E)
    (hc : ‖c‖ ≤ 1 / 2) (hfix : ∀ n : ℕ, 1 ≤ n → (R ^ n) c ≠ c) :
    ∃ ρ : E ≃ᵢ E,
      (∀ n : ℕ, (ρ ^ n) 0 ∈ Metric.closedBall (0 : E) 1) ∧
      (∀ n : ℕ, 1 ≤ n → (ρ ^ n) 0 ≠ 0)  := by
  obtain ⟨ρ, hρ⟩ := exists_conjugated_isometry R c
  have horbit := conjugate_orbit_formula ρ R c hρ
  refine ⟨ρ, ?_, ?_⟩
  · intro n
    rw [Metric.mem_closedBall, dist_zero_right, horbit n]
    exact conjugate_orbit_norm_bound R c hc n
  · intro n hn
    rw [horbit n]
    exact conjugate_orbit_ne_zero R c hfix n hn

end Problems.Geometry.banach_tarski
