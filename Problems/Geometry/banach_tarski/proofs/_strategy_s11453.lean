import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_zaxis_bad_angles_countable

namespace Problems.Geometry.banach_tarski

-- Hilbert-hotel z-axis angle choice (z-axis analogue of good_angle_avoids_collisions / s11432).
-- Sole brick: the "bad" set B = {θ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0} is countable
-- [proved sibling zaxis_bad_angles_countable]. The "∃ θ ∉ B" step is inlined (countable B ≠ univ
-- since ℝ is uncountable). Combinator: take θ ∉ B; for p ∈ D, landing on the z-axis would witness
-- membership in B, contradiction.
theorem s11453
    (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (hcol : ∀ p ∈ D, {θ : ℝ | (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable) :
    ∃ θ : ℝ, ∀ p ∈ D, ¬ ((R θ p) 0 = 0 ∧ (R θ p) 1 = 0)  := by
  have hB : {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0}.Countable :=
    zaxis_bad_angles_countable D hD R hcol
  obtain ⟨θ, hθ⟩ : ∃ θ : ℝ,
      θ ∉ {θ : ℝ | ∃ p ∈ D, (R θ p) 0 = 0 ∧ (R θ p) 1 = 0} := by
    by_contra h
    push_neg at h
    exact Cardinal.not_countable_real (by rwa [Set.eq_univ_of_forall h] at hB)
  refine ⟨θ, ?_⟩
  intro p hp hcontra
  exact hθ ⟨p, hp, hcontra.1, hcontra.2⟩

end Problems.Geometry.banach_tarski
