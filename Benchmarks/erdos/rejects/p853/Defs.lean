import Mathlib

set_option maxHeartbeats 400000

open Filter

namespace Problems.Erdos.p853

noncomputable def r (x : ℕ) : ℕ :=
  sInf { t : ℕ | 0 < t ∧ t % 2 = 0 ∧ ¬ (∃ n ≤ x, primeGap n = t) }

end Problems.Erdos.p853
