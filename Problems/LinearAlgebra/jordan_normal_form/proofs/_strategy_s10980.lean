import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10980 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q) :
    ∃ (p : ℕ) (g : Fin p → Fin n), StrictMono g ∧ ∀ q : Fin n, S q ↔ q ∈ Set.range g  := by
  classical
  let T : Finset (Fin n) := Finset.univ.filter S
  refine ⟨T.card, T.orderEmbOfFin rfl, (T.orderEmbOfFin rfl).strictMono, ?_⟩
  intro q
  rw [Finset.range_orderEmbOfFin]
  simp [T]

end Problems.LinearAlgebra.jordan_normal_form
