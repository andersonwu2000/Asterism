import Mathlib
import Problems.wilson.Defs
import Problems.wilson.proofs._strategy_s122

namespace Problems.wilson

theorem main : ∀ p : ℕ, p.Prime → Nat.factorial (p - 1) % p = p - 1 := s122

end Problems.wilson
