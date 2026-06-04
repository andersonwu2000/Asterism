-- Factorize `a^3 + 1 = (a+1) * (a^2 - a + 1)`, then split divisibility:
--   `3^(n+1) ∣ a+1` (parent hypothesis) and `3 ∣ a^2 - a + 1` (mod-3 arithmetic
--   from `3 ∣ a+1`).  Multiplying gives `3^(n+2) = 3^(n+1) * 3 ∣ a^3 + 1`.
-- Sub-goal `cube_factor` drops `n` and the divisibility hypothesis (pure ring
-- identity in ℕ with subtraction).  Sub-goal `three_dvd_quad` drops `n` and the
-- `1 ≤ a` premise (mod-3 argument on `a+1 ≡ 0`).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9802

namespace Problems.Minif2f.imo_1990_p3

def lifting_three_pow := @Problems.Minif2f.imo_1990_p3.s9802

end Problems.Minif2f.imo_1990_p3
