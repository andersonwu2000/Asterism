import Mathlib

namespace Problems.wilson

theorem s122_sub_1 : ∀ p : ℕ, p.Prime → (↑(Nat.factorial (p - 1)) : ZMod p) = -1 := by
  intro p hp
  have ne_one : p ≠ 1 := by
    have := Nat.Prime.two_le hp
    omega
  exact (Nat.prime_iff_fac_equiv_neg_one ne_one).mp hp
