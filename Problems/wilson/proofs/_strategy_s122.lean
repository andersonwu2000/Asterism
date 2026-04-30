import Problems.wilson.proofs.L_s122_sub_1
import Problems.wilson.proofs.L_s122_sub_2
import Problems.wilson.proofs.L_s122_sub_3

namespace Problems.wilson

theorem s122 : ∀ p : ℕ, p.Prime → Nat.factorial (p - 1) % p = p - 1 := by
  intro p hp
  have h1 : (↑(Nat.factorial (p - 1)) : ZMod p) = -1 := s122_sub_1 p hp
  have h2 : (-1 : ZMod p).val = p - 1 := s122_sub_2 p hp
  have h_pos : 0 < p := by
    have : 2 ≤ p := Nat.Prime.two_le hp
    omega
  have h3 : (↑(Nat.factorial (p - 1)) : ZMod p).val = Nat.factorial (p - 1) % p :=
    s122_sub_3 p h_pos
  rw [← h3, h1, h2]
