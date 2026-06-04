-- Use the already-abstract `pushforward_d_eq` identity:
--   N (∑ gᵢ • vᵢ) = ∑_{ti} g⟨inl ti.1, ti.2.succ⟩ • d⟨ti.1.1, ti.2⟩
-- Then `hg : ∑ gᵢ • vᵢ = 0` collapses the LHS via `map_zero`, giving the goal.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11036

namespace Problems.LinearAlgebra.jordan_normal_form

def pushforward_d_relation := @Problems.LinearAlgebra.jordan_normal_form.s11036

end Problems.LinearAlgebra.jordan_normal_form
