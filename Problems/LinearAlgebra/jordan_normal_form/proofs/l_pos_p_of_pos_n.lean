import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- pos_p_of_pos_n: if n > 0 then the strict-mono enumeration g of S-starts is nonempty
-- because q=0 always satisfies S (by h0), lives in range g (by hrange), so some t:Fin p exists.
theorem pos_p_of_pos_n {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    0 < n → 0 < p := by
  intro hn
  have hq : (⟨0, hn⟩ : Fin n) ∈ Set.range g := (hrange _).mp (h0 _ rfl)
  obtain ⟨t, _⟩ := hq
  exact Nat.lt_of_le_of_lt (Nat.zero_le t.val) t.isLt

end Problems.LinearAlgebra.jordan_normal_form
