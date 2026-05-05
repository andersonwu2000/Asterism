import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
open Classical in
theorem s84_sub_1 (P : Finset (ℝ × ℝ))
    (h_noncol : ∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c)
    (h_skolem : ∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q)
    (h_witness : ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r)
    (h_nonempty : ((P ×ˢ P ×ˢ P).filter
        (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
          t.1 ≠ t.2.1 ∧ ¬ Collinear t.1 t.2.1 t.2.2)).Nonempty) :
    ∀ p' ∈ P, ∀ q' ∈ P, ∀ r' ∈ P, p' ≠ q' → ¬ Collinear p' q' r' →
      ((p', q', r') : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ)) ∈
        ((P ×ˢ P ×ˢ P).filter
          (fun t : (ℝ × ℝ) × (ℝ × ℝ) × (ℝ × ℝ) =>
            t.1 ≠ t.2.1 ∧ ¬ Collinear t.1 t.2.1 t.2.2)) := by simp_all

end Problems.sylvester_gallai
