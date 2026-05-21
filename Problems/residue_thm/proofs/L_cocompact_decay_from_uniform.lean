-- Pick M := 2 * π * (R/2) * C and split into:
-- (A) Cocompact-eventual far-field: R/2 < ‖z - z₀‖ eventually as z escapes compacts.
-- (B) Pointwise length×sup bound: at any z with R/2 < ‖z - z₀‖, the circle integral
--     ‖∮ w in C(z₀, R/2), f w / (w - z)‖ is bounded by M / (‖z - z₀‖ - R/2)
--     (reverse triangle on the sphere gives ‖w - z‖ ≥ ‖z - z₀‖ - R/2 > 0, so
--     ‖f w / (w - z)‖ ≤ C / (‖z - z₀‖ - R/2); circle length 2π·(R/2) finishes).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10441

namespace Problems.residue_thm

def cocompact_decay_from_uniform := @Problems.residue_thm.s10441

end Problems.residue_thm
