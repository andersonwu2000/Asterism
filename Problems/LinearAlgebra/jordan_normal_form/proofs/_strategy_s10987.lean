import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_from_boundaries_2
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_pos_p_of_pos_n
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_start_enum_zero

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10987 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (g t : ℕ)) := by sorry

end Problems.LinearAlgebra.jordan_normal_form
