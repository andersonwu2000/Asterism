import Mathlib
import Problems.wilson.Defs

namespace Problems.wilson

theorem main_sub_1 : ∀ p : ℕ, p.Prime → (Nat.factorial (p - 1) : ZMod p) = -1 := by
  intro p hp
  exact (Nat.prime_iff_fac_equiv_neg_one hp.ne_one).mp hp

end Problems.wilson
