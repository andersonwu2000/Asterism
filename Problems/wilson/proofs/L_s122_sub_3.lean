import Mathlib

namespace Problems.wilson

theorem s122_sub_3 : ∀ p : ℕ, p > 0 → (↑(Nat.factorial (p - 1)) : ZMod p).val = Nat.factorial (p - 1) % p := by
  intro p _
  exact ZMod.val_natCast p (Nat.factorial (p - 1))

end Problems.wilson
