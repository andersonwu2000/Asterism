import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_gaps_from_boundary
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_pos_p_when_pos_n
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_start_enum_at_zero

namespace Problems.LinearAlgebra.jordan_normal_form

-- Instantiate `gaps_from_boundary` at `b t := (g t : ℕ)`.
-- Premises:
--  * StrictMono b ← `hmono` (Fin order is val-defined)
--  * b t < n ← `Fin.isLt`
--  * t = 0 → b t = 0 ← sub-goal `start_enum_at_zero`
--  * 0 < n → 0 < p ← sub-goal `pos_p_when_pos_n`
theorem s11032 {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = (g t : ℕ))  := by
  exact gaps_from_boundary (fun t => (g t : ℕ))
    (fun a b hab => hmono hab)
    (fun t => (g t).isLt)
    (start_enum_at_zero S h0 p g hmono hrange)
    (pos_p_when_pos_n S h0 p g hmono hrange)

end Problems.LinearAlgebra.jordan_normal_form
