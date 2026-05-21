import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_winding_quot_injective
import Problems.pi1_circle.proofs.L_winding_quot_surjective

namespace Problems.pi1_circle

open Real

-- Split `Function.Bijective W'` into injectivity and surjectivity sub-goals.
-- Each carries the same `h_char` hypothesis; `⟨·,·⟩` reassembles `Bijective`.
theorem s10693
    (W' : Path.Homotopic.Quotient (1 : Circle) 1 → ℤ)
    (h_char : ∀ (γ : Path (1 : Circle) 1),
        Circle.isCoveringMap_exp.liftPath γ.toContinuousMap 0
            (by simp : γ.toContinuousMap 0 = Circle.exp 0) 1 = (W' ⟦γ⟧ : ℝ) * (2 * π)) :
    Function.Bijective W'  := by
  have h_inj := winding_quot_injective W' h_char
  have h_surj := winding_quot_surjective W' h_char
  exact ⟨h_inj, h_surj⟩

end Problems.pi1_circle
