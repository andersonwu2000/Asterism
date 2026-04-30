import Mathlib.Data.Nat.Prime.Basic

namespace Problems.wilson

theorem s124_sub_1 : ∀ p : ℕ, p.Prime → 2 ≤ p := by
  intro p hp
  exact Nat.Prime.two_le hp
