import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs.L_algebraic_identity
import Problems.Minif2f.imo_1984_p2.proofs.L_seven_cube_from_factorization

namespace Problems.Minif2f.imo_1984_p2

-- Two-step decomposition via the factorization
--   (a+b)^7 - a^7 - b^7 = 7·a·b·(a+b)·(a²+a·b+b²)².
-- Sub-goal `algebraic_identity` is the pure ring identity (leaf for `ring`).
-- Sub-goal `seven_cube_from_factorization` performs the prime-power cancellation:
-- peel off the coprime factor 7·a·b·(a+b) leaving 7^6 ∣ (a²+a·b+b²)², then
-- take the prime-power square-root to obtain 7^3 ∣ a²+a·b+b².
theorem s9371 :
    ∀ (a b : ℤ), ¬7 ∣ a → ¬7 ∣ b → ¬7 ∣ a + b →
      7 ^ 7 ∣ (a + b) ^ 7 - a ^ 7 - b ^ 7 →
      (7:ℤ) ^ 3 ∣ a ^ 2 + a * b + b ^ 2  := by
  intro a b ha hb hab hdvd
  have h_id := algebraic_identity a b
  exact seven_cube_from_factorization a b ha hb hab (h_id ▸ hdvd)

end Problems.Minif2f.imo_1984_p2
