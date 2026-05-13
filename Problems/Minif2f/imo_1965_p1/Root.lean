-- Chain h₂ ≤ h₃ to get 2·cos x ≤ √2, hence cos x ≤ √2/2; then split the
-- conjunction into the two arc bounds, each phrased with explicit `Real.pi`
-- (the new_*.lean stubs lack `open Real`, so bare `π` would auto-bind there).
-- Adding `open Real` here makes the signature's bare `π` resolve to `Real.pi`,
-- which is what the parent `main` expects.
import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs._strategy_s9707

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

def main := @Problems.Minif2f.imo_1965_p1.s9707

end Problems.Minif2f.imo_1965_p1
