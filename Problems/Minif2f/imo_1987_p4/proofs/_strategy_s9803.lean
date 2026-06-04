import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs

namespace Problems.Minif2f.imo_1987_p4

-- Direct proof via `Finset.card_bij` with the involution `a ↦ g a`.
-- Maps_to / inj_on / surj_on all reduce to one `hgg` application + `omega`.
theorem s9803 :
    ∀ (g : ℕ → ℕ), (∀ a, a < 1987 → g a < 1987) →
      (∀ a, a < 1987 → g (g a) = a) →
      (Finset.filter (fun a => a < g a) (Finset.range 1987)).card
        = (Finset.filter (fun a => g a < a) (Finset.range 1987)).card  := by
  intro g hg hgg
  apply Finset.card_bij (fun a _ => g a)
  · intro a ha
    simp only [Finset.mem_filter, Finset.mem_range] at ha ⊢
    obtain ⟨ha1, ha2⟩ := ha
    have hi := hgg a ha1
    refine ⟨hg a ha1, ?_⟩
    omega
  · intro a₁ ha₁ a₂ ha₂ heq
    simp only [Finset.mem_filter, Finset.mem_range] at ha₁ ha₂
    have h1 := hgg a₁ ha₁.1
    have h2 := hgg a₂ ha₂.1
    have : g (g a₁) = g (g a₂) := by rw [heq]
    rw [h1, h2] at this
    exact this
  · intro b hb
    simp only [Finset.mem_filter, Finset.mem_range] at hb
    obtain ⟨hb1, hb2⟩ := hb
    have hi := hgg b hb1
    refine ⟨g b, ?_, hi⟩
    simp only [Finset.mem_filter, Finset.mem_range]
    refine ⟨hg b hb1, ?_⟩
    omega

end Problems.Minif2f.imo_1987_p4
