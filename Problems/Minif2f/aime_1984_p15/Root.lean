-- Direct closure via `linear_combination` with Lagrange-interpolation coefficients.
-- Setting s ∈ {4,16,36,64} in
--   (s-1)(s-9)(s-25)(s-49) = (s-4)(s-16)(s-36)(s-64)
--     + α(s-16)(s-36)(s-64) + β(s-4)(s-36)(s-64)
--     + γ(s-4)(s-16)(s-64) + δ(s-4)(s-16)(s-36)
-- yields α = 315/512, β = 693/256, γ = 3861/512, δ = 6435/256
-- whose sum equals 36 — exactly the conclusion. No sub-goals required.
import Mathlib
import Problems.Minif2f.aime_1984_p15.Defs
import Problems.Minif2f.aime_1984_p15.proofs._strategy_s767

namespace Problems.Minif2f.aime_1984_p15

def main := @Problems.Minif2f.aime_1984_p15.s767

end Problems.Minif2f.aime_1984_p15
