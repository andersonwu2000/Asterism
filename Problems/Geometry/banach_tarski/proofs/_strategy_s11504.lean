import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_pairwise_disjoint_of_shift_disjoint
import Problems.Geometry.banach_tarski.proofs.L_exists_bounded_injective_origin_orbit

namespace Problems.Geometry.banach_tarski

-- Absorb {0} via an off-origin isometry ρ whose 0-orbit stays in the ball and never
-- returns to 0.  Reduce the Set-level claim to a pointwise existence:
-- exists_bounded_injective_origin_orbit gives ρ with `(ρ^n) 0 ∈ ball` (⊆-part, after
-- `image_singleton` + `iUnion_subset`) and `(ρ^n) 0 ≠ 0` for n≥1 (the shift-disjointness
-- `Disjoint ((ρ^n)''{0}) {0}`), fed through the proved pairwise_disjoint_of_shift_disjoint
-- (s11430) to upgrade single shifts to the full ℕ-indexed Pairwise family.
theorem s11504 :
    ∃ ρ : E ≃ᵢ E,
      (⋃ n : ℕ, (ρ ^ n) '' ({0} : Set E)) ⊆ Metric.closedBall (0 : E) 1 ∧
      Pairwise (fun i j : ℕ =>
        Disjoint ((ρ ^ i) '' ({0} : Set E)) ((ρ ^ j) '' ({0} : Set E)))  := by
  have h_orbit := exists_bounded_injective_origin_orbit
  obtain ⟨ρ, hball, hne⟩ := h_orbit
  refine ⟨ρ, ?_, ?_⟩
  · apply Set.iUnion_subset
    intro n
    rw [Set.image_singleton]
    intro x hx
    rw [Set.mem_singleton_iff] at hx
    subst hx
    exact hball n
  · apply pairwise_disjoint_of_shift_disjoint ρ ({0} : Set E)
    intro n hn
    rw [Set.image_singleton]
    rw [Set.disjoint_singleton]
    exact hne n hn

end Problems.Geometry.banach_tarski
