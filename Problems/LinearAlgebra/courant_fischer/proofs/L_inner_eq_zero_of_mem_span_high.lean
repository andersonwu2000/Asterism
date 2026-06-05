-- Orthonormality: x in span of bottom modes {b_j : m ≤ j} is ⟂ to b_i for i < m.
-- span_induction on the membership; the linear functional ⟪b i, ·⟫ vanishes on each
-- generator b_j (i ≠ j since i < m ≤ j by orthonormality) and is closed under +/•.
-- Direct leaf — no sub-goals.
import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs
import Problems.LinearAlgebra.courant_fischer.proofs._strategy_s11631

namespace Problems.LinearAlgebra.courant_fischer

def inner_eq_zero_of_mem_span_high := @Problems.LinearAlgebra.courant_fischer.s11631

end Problems.LinearAlgebra.courant_fischer
