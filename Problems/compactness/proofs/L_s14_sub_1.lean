import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Atom case of the truth-lemma induction: canonical valuation satisfies atom a iff atom a ∈ M.
theorem s14_sub_1 {α : Type} (M : Set (PropForm α)) (a : α) :
    PropForm.atom a ∈ M ↔
    PropForm.eval (fun a' => decide (PropForm.atom a' ∈ M)) (PropForm.atom a) = true := by
  simp only [PropForm.eval, decide_eq_true_eq]

end Problems.compactness
