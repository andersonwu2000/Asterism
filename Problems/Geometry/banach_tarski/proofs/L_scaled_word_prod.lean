-- Factor the scalar `(1/3)` out of the word product by induction on the list.
-- Each generator equals `(1/3) •` its un-normalized integer matrix (hypotheses
-- `hA … hBInv`), so the head term `f x = (1/3) • g x` (via `← smul_ite` collecting
-- the branches), and the cons step combines `(r • _) * (s • _) = (r*s) • (_ * _)`
-- through `smul_mul_assoc`, `mul_smul_comm`, `smul_smul`, matching `pow_succ'`.
-- Direct leaf proof — no sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11409

namespace Problems.Geometry.banach_tarski

def scaled_word_prod := @Problems.Geometry.banach_tarski.s11409

end Problems.Geometry.banach_tarski
