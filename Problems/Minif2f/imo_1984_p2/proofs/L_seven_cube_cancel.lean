-- Two-step prime cancellation: first peel the single factor of 7 plus the three
-- coprime-to-7 factors (x, y, x+y) to land at 7^6 ∣ Q^2; then use the prime-square
-- valuation lemma to halve the exponent, yielding 7^3 ∣ Q where Q = x^2+x*y+y^2.
import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs._strategy_s9483

namespace Problems.Minif2f.imo_1984_p2

def seven_cube_cancel := @Problems.Minif2f.imo_1984_p2.s9483

end Problems.Minif2f.imo_1984_p2
