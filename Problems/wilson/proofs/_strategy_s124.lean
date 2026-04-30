import Problems.wilson.proofs.L_s124_sub_1
import Problems.wilson.proofs.L_s124_sub_2
import Problems.wilson.proofs.L_s124_sub_3

namespace Problems.wilson

theorem s124 : ∀ p : ℕ, p.Prime → (-1 : ZMod p).val = p - 1 := by
  intro p hp
  have h1 : 2 ≤ p := s124_sub_1 p hp
  have h2 : 0 < p := s124_sub_2 p h1
  exact s124_sub_3 p h2
