import Mathlib

set_option maxHeartbeats 400000

namespace Problems.Erdos.p313

def erdos313Solutions : Set (ℕ × Finset ℕ) :=
  {(m, P) | 2 ≤ m ∧ P.Nonempty ∧ (∀ p ∈ P, p.Prime) ∧ ∑ p ∈ P, (1 : ℚ) / p = 1 - 1 / m}

def IsPrimaryPseudoperfect (n : ℕ) : Prop := ∃ P, (n, P) ∈ erdos313Solutions

end Problems.Erdos.p313
