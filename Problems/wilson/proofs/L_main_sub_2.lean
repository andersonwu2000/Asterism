import Mathlib
import Problems.wilson.Defs

namespace Problems.wilson

theorem main_sub_2 : ∀ p : ℕ, p.Prime → ZMod.val ((-1 : ZMod p)) = p - 1 := by
  intro p hp
  have hp2 : 2 ≤ p := hp.two_le
  obtain ⟨n, rfl⟩ : ∃ n, p = n + 1 := ⟨p - 1, by omega⟩
  simp [ZMod.val_neg_one]

end Problems.wilson
