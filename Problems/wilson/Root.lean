import Mathlib
import Problems.wilson.proofs.L_main_sub_1
import Problems.wilson.proofs.L_main_sub_2
import Problems.wilson.proofs.L_main_sub_3
import Problems.wilson.proofs.L_main_sub_4

namespace Problems.wilson

theorem main : ∀ p : ℕ, p.Prime → Nat.factorial (p - 1) % p = p - 1 := by
  intro p hp
  have h1 : Nat.factorial (p - 1) % p = ZMod.val (↑(Nat.factorial (p - 1)) : ZMod p) :=
    main_sub_1 p hp
  have h2 : (↑(Nat.factorial (p - 1)) : ZMod p) = ∏ x : (ZMod p)ˣ, (x : ZMod p) :=
    main_sub_2 p hp
  have h3 : ∏ x : (ZMod p)ˣ, (x : ZMod p) = -1 :=
    main_sub_3 p hp
  have h4 : ZMod.val (-1 : ZMod p) = p - 1 :=
    main_sub_4 p hp
  rw [h1, h2, h3]
  exact h4

end Problems.wilson
