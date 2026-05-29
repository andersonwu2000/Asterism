import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_bad_angles_countable

namespace Problems.Geometry.banach_tarski

-- Hilbert-hotel angle choice: ρ := R θ for a θ outside the countable "bad" set
-- B of angles causing a collision R(nθ)·p = q (n≥1, p,q ∈ D).
-- Sole sub-goal: B is countable [bad_angles_countable]. The "∃ θ ∉ B" step is
-- inlined (countable B ≠ univ since ℝ is uncountable) to dodge the dedupe-probe
-- leaf misfire. Combinator: take θ ∉ B, ρ := R θ; ρ0=0 by h0; disjointness is
-- exactly θ ∉ B via hpow.
theorem s11432 (D : Set E) (hD : D.Countable)
    (R : ℝ → (E ≃ᵢ E))
    (h0 : ∀ θ : ℝ, R θ 0 = 0)
    (hpow : ∀ (θ : ℝ) (n : ℕ), (R θ) ^ n = R ((n : ℝ) * θ))
    (hcol : ∀ p ∈ D, ∀ q ∈ D, {θ : ℝ | R θ p = q}.Countable) :
    ∃ ρ : E ≃ᵢ E, ρ 0 = 0 ∧ ∀ n : ℕ, 1 ≤ n → Disjoint ((ρ ^ n) '' D) D  := by
  have hB : {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q}.Countable :=
    bad_angles_countable D hD R hcol
  obtain ⟨θ, hθ⟩ : ∃ θ : ℝ,
      θ ∉ {θ : ℝ | ∃ n : ℕ, 1 ≤ n ∧ ∃ p ∈ D, ∃ q ∈ D, R ((n : ℝ) * θ) p = q} := by
    by_contra h
    push_neg at h
    exact Cardinal.not_countable_real (by rwa [Set.eq_univ_of_forall h] at hB)
  refine ⟨R θ, h0 θ, ?_⟩
  intro n hn
  rw [Set.disjoint_left]
  rintro x ⟨p, hp, rfl⟩ hx
  exact hθ ⟨n, hn, p, hp, (R θ ^ n) p, hx, by rw [hpow]⟩
end Problems.Geometry.banach_tarski
