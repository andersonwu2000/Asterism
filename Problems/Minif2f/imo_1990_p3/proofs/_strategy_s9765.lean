import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lifting_base
import Problems.Minif2f.imo_1990_p3.proofs.L_three_lifting_step

namespace Problems.Minif2f.imo_1990_p3

-- Induction on k. Base case (k=0) reduces to 3 ∣ 2^m + 1 (m odd).
-- Inductive step: from 3^(k+1) ∣ 2^(3^k*m)+1, lift to 3^(k+2) ∣ 2^(3^(k+1)*m)+1
-- via the factorization a^3 + 1 = (a+1)(a^2 - a + 1) with 3 ∣ a^2 - a + 1.
theorem s9765 :
    ∀ (k m : ℕ), Odd m → ¬ (3 ∣ m) → 3 ^ (k + 1) ∣ 2 ^ (3 ^ k * m) + 1  := by
  intro k
  induction k with
  | zero =>
    intro m hm h3
    exact three_lifting_base m hm h3
  | succ k ih =>
    intro m hm h3
    exact three_lifting_step k m hm h3 (ih m hm h3)

end Problems.Minif2f.imo_1990_p3
