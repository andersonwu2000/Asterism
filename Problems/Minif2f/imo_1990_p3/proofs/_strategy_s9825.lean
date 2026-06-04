import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_two_sq_eq_one_given_no_seven

namespace Problems.Minif2f.imo_1990_p3

-- Refute `p ∣ m` by reducing to the ZMod identity `(2:ZMod p)^2 = 1`, then
-- inline the standard `p ∣ 3` contradiction (since `prime_ge_five_not_two_sq_eq_one`
-- is not auto-imported here). Sub-goal `two_sq_eq_one_given_no_seven` carries the
-- entire order-of-2 / gcd(2m,p-1)=2 argument; ¬7∣m collapses the only case where
-- gcd-of-2 fails (p=7 with 3∣m forcing gcd(2m,p-1)=6 ⊃ 2).
theorem s9825 :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → ¬ p ∣ m  := by
  intro m hm hdvd h3 h9 h7 p hp hge hpm
  haveI : Fact p.Prime := ⟨hp⟩
  have h_two_sq : (2 : ZMod p) ^ 2 = 1 :=
    two_sq_eq_one_given_no_seven m hm hdvd h3 h9 h7 p hp hge hpm
  have h3z : (3 : ZMod p) = 0 := by linear_combination h_two_sq
  have hcast : ((3 : ℕ) : ZMod p) = 0 := by exact_mod_cast h3z
  have hdvd3 : p ∣ 3 := (CharP.cast_eq_zero_iff (ZMod p) p 3).mp hcast
  have hle : p ≤ 3 := Nat.le_of_dvd (by norm_num) hdvd3
  omega

end Problems.Minif2f.imo_1990_p3
