-- Conjugate a small-vector linear rotation `R` by the translation `x ↦ x - c`:
-- `ρ x = R (x - c) + c` is an isometry whose origin-orbit satisfies `(ρ ^ n) 0 = c - R ^ n c`.
-- Sub-goals: (1) build the conjugated isometry with that pointwise formula;
-- (2) the closed-form orbit by induction; (3) the orbit lies in the unit ball
-- (`‖c - R ^ n c‖ ≤ 2‖c‖ ≤ 1`); (4) it never returns to `0` for `n ≥ 1` (from `hfix`).
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11513

namespace Problems.Geometry.banach_tarski

def conjugate_origin_orbit := @Problems.Geometry.banach_tarski.s11513

end Problems.Geometry.banach_tarski
