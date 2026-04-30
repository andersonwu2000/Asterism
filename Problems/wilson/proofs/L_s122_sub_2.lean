import Mathlib
import Problems.wilson.Defs
import Problems.wilson.proofs._strategy_s124

namespace Problems.wilson

theorem s122_sub_2 : ∀ p : ℕ, p.Prime → (-1 : ZMod p).val = p - 1 := s124

end Problems.wilson
