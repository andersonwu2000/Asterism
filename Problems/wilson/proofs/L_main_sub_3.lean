import Mathlib
import Problems.wilson.Defs

namespace Problems.wilson

theorem main_sub_3 : ∀ p : ℕ, p.Prime →
    ZMod.val ((Nat.factorial (p - 1) : ZMod p)) = Nat.factorial (p - 1) % p := by simp

end Problems.wilson
