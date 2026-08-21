import Mathlib

set_option maxHeartbeats 400000

namespace Problems.Erdos.p1113

def HasFinitePrimeCoveringSet (k : ℕ) : Prop :=
  ∃ P : Finset ℕ, (∀ p ∈ P, p.Prime) ∧ ∀ n, ∃ p ∈ P, p ∣ (k * 2 ^ n + 1)

end Problems.Erdos.p1113
