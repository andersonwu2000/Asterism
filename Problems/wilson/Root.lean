import Mathlib
import Problems.wilson.proofs.L_main_sub_1
import Problems.wilson.proofs.L_main_sub_2
import Problems.wilson.proofs.L_main_sub_3

namespace Problems.wilson

theorem main : ∀ p : ℕ, p.Prime → Nat.factorial (p - 1) % p = p - 1 := by
  intro p hp
  have h1 : (Nat.factorial (p - 1) : ZMod p) = -1 := main_sub_1 p hp
  have h2 : ZMod.val ((-1 : ZMod p)) = p - 1 := main_sub_2 p hp
  have h3 : ZMod.val ((Nat.factorial (p - 1) : ZMod p)) = Nat.factorial (p - 1) % p :=
    main_sub_3 p hp
  rw [← h3, h1, h2]

end Problems.wilson
