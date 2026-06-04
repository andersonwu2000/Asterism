import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_min_fac_dvd_three_of_two_sq_eq_one
import Problems.Minif2f.imo_1990_p3.proofs.L_two_sq_eq_one_mod_min_fac

namespace Problems.Minif2f.imo_1990_p3

-- Decompose via "order of 2 in ZMod p divides 2", where p = Nat.minFac n.
-- (a) `two_sq_eq_one_mod_min_fac` (Backward, heart of the argument):
--     under all hypotheses, `(2 : ZMod p)^2 = 1`. This packages the
--     entire FLT + cyclic-order chain: p | n ⇒ 2^(2n) ≡ 1 mod p, plus
--     orderOf 2 ∣ gcd(2n, p-1) which the coprime hypothesis collapses to 2.
-- (b) `min_fac_dvd_three_of_two_sq_eq_one` (Builder, translation):
--     `(2 : ZMod p)^2 = 1` rewrites to `(3 : ZMod p) = 0`, i.e. `p ∣ 3`
--     via `ZMod.natCast_zmod_eq_zero_iff_dvd`.
theorem s9647 : ∀ (n : ℕ), 2 ≤ n → n ^ 2 ∣ 2 ^ n + 1 → Nat.Coprime n (Nat.minFac n - 1) → Nat.minFac n ∣ 3  := by
  intro n hn hdvd hcop
  have h_two_sq := two_sq_eq_one_mod_min_fac n hn hdvd hcop
  exact min_fac_dvd_three_of_two_sq_eq_one n hn hdvd hcop h_two_sq

end Problems.Minif2f.imo_1990_p3
