import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- Direct: (R θ)^n = R(n·θ) by hpow, and hno says R(n·θ) maps D outside D.
-- Disjoint via Set.disjoint_left: any x in the image equals R(n·θ) p with p∈D,
-- so x∈D contradicts hno.
theorem s11446
    (D : Set E) (R : ℝ → (E ≃ᵢ E)) (θ : ℝ)
    (hpow : ∀ (φ : ℝ) (n : ℕ), (R φ) ^ n = R ((n : ℝ) * φ))
    (hno : ∀ n : ℕ, 1 ≤ n → ∀ p ∈ D, ∀ q ∈ D, R ((n : ℝ) * θ) p ≠ q) :
    ∀ n : ℕ, 1 ≤ n → Disjoint ((R θ ^ n) '' D) D  := by
  intro n hn
  rw [Set.disjoint_left]
  rintro x ⟨p, hp, rfl⟩ hxD
  rw [hpow θ n] at hxD
  exact hno n hn p hp (R ((n : ℝ) * θ) p) hxD rfl

end Problems.Geometry.banach_tarski
