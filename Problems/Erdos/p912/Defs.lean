import Mathlib

set_option maxHeartbeats 400000

open scoped Nat Asymptotics
open Filter

namespace Problems.Erdos.p912

noncomputable def h (n : ℕ) : ℕ := (n !).factorization.frange.card

end Problems.Erdos.p912
