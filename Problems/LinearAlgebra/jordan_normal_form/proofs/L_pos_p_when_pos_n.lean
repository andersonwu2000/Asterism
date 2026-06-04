import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- pos_p_when_pos_n: 0 < n implies 0 < p by finding element 0 in range g via h0 + hrange
theorem pos_p_when_pos_n {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    0 < n → 0 < p := by
  intro hn
  have hq : (⟨0, hn⟩ : Fin n) ∈ Set.range g := (hrange ⟨0, hn⟩).mp (h0 ⟨0, hn⟩ rfl)
  obtain ⟨i, _⟩ := hq
  exact Nat.pos_of_ne_zero (Fin.pos i).ne'

end Problems.LinearAlgebra.jordan_normal_form
