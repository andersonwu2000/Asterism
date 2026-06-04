-- Instantiate `gaps_from_boundary` at `b t := (g t : ℕ)`.
-- Premises:
--  * StrictMono b ← `hmono` (Fin order is val-defined)
--  * b t < n ← `Fin.isLt`
--  * t = 0 → b t = 0 ← sub-goal `start_enum_at_zero`
--  * 0 < n → 0 < p ← sub-goal `pos_p_when_pos_n`
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11032

namespace Problems.LinearAlgebra.jordan_normal_form

def gaps_for_starts := @Problems.LinearAlgebra.jordan_normal_form.s11032

end Problems.LinearAlgebra.jordan_normal_form
