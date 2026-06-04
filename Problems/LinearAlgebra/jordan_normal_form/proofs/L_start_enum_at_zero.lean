import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- start_enum_at_zero: if g is StrictMono with range = S, and S contains the
-- zeroth element, then g 0 = 0
theorem start_enum_at_zero {n : ℕ} (S : Fin n → Prop)
    (h0 : ∀ q : Fin n, (q : ℕ) = 0 → S q)
    (p : ℕ) (g : Fin p → Fin n) (hmono : StrictMono g)
    (hrange : ∀ q : Fin n, S q ↔ q ∈ Set.range g) :
    ∀ t : Fin p, (t : ℕ) = 0 → (g t : ℕ) = 0 := by
  intro t ht
  have hn : 0 < n := Nat.lt_of_le_of_lt (Nat.zero_le _) (g t).isLt
  have hS0 : S ⟨0, hn⟩ := h0 ⟨0, hn⟩ rfl
  obtain ⟨t', ht'⟩ := (hrange ⟨0, hn⟩).mp hS0
  -- ht' : g t' = ⟨0, hn⟩
  have ht'val : (t' : ℕ) = 0 := by
    by_contra h
    have h_pos : 0 < (t' : ℕ) := Nat.pos_of_ne_zero h
    have hp' : 0 < p := Nat.lt_trans h_pos t'.isLt
    have hlt : (⟨0, hp'⟩ : Fin p) < t' := Fin.mk_lt_mk.mpr h_pos
    have hlt2 := hmono hlt
    rw [Fin.lt_def] at hlt2
    simp [ht'] at hlt2
  have htval_eq : t = t' := Fin.ext (by omega)
  rw [htval_eq, ht']

end Problems.LinearAlgebra.jordan_normal_form