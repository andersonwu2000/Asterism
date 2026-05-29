import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_swierczkowski_integer_residue_classified

namespace Problems.Geometry.banach_tarski

-- Strengthen the existence-only `¬3∣q` claim to the full per-first-letter residue
-- classification (Strategist directive: bare `∃ p q r, ¬3∣q` is NON-inductive since
-- `q' = 4p+q ≡ p+q (mod 3)` is unpinned by `q ≢ 0` alone). The strengthened sub-goal
-- `swierczkowski_integer_residue_classified` carries the head-keyed residue disjunction
-- making the leftmost-letter induction close; the parent just projects out `¬3∣q`.
theorem s11394
    (step : Fin 2 × Bool → ℤ × ℤ × ℤ → ℤ × ℤ × ℤ)
    (hstep : ∀ p q r : ℤ,
        step (0, true)  (p, q, r) = (p - 2 * q, 4 * p + q, 3 * r) ∧
        step (0, false) (p, q, r) = (p + 2 * q, -4 * p + q, 3 * r) ∧
        step (1, true)  (p, q, r) = (3 * p, q - 4 * r, 2 * q + r) ∧
        step (1, false) (p, q, r) = (3 * p, q + 4 * r, -2 * q + r))
    (w : FreeGroup (Fin 2)) (hw : FreeGroup.toWord w ≠ []) :
    ∃ p q r : ℤ,
      List.foldr step (0, 1, 0) (FreeGroup.toWord w) = (p, q, r) ∧ ¬ (3 : ℤ) ∣ q  := by
  obtain ⟨p, q, r, hfold, hq, _⟩ :=
    swierczkowski_integer_residue_classified step hstep w hw
  exact ⟨p, q, r, hfold, hq⟩




end Problems.Geometry.banach_tarski
