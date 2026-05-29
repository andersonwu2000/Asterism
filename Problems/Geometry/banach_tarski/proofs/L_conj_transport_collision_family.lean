import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_reduce_cons_tail_reduced

namespace Problems.Geometry.banach_tarski

-- entry_kind: Backward
theorem conj_transport_collision_family
    (D : Set E) (R₀ : ℝ → (E ≃ᵢ E)) (g : E ≃ᵢ E)
    (h0₀ : ∀ θ : ℝ, R₀ θ 0 = 0)
    (hpow₀ : ∀ (θ : ℝ) (n : ℕ), (R₀ θ) ^ n = R₀ ((n : ℝ) * θ))
    (hcol₀ : ∀ p : E, ¬ (p 0 = 0 ∧ p 1 = 0) → ∀ q : E, {θ : ℝ | R₀ θ p = q}.Countable)
    (hg0 : g 0 = 0) (hgoff : ∀ p ∈ D, ¬ ((g p) 0 = 0 ∧ (g p) 1 = 0)) :
    ∃ R : ℝ → (E ≃ᵢ E),
      (∀ θ : ℝ, R θ 0 = 0) ∧
      (∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ)) ∧
      (∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) := by apply reduce_cons_tail_reduced <;> assumption

end Problems.Geometry.banach_tarski
