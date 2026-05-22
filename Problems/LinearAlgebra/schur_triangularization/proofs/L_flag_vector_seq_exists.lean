-- Decompose into (1) the dimensional step-existence lemma — given any submodule U ≤ W(j+1)
-- of dimension j, there is a vector in W(j+1) outside U — and (2) a recursive construction
-- that consumes that step-existence to build the full Fin n → V sequence and proves the
-- initial-span equality by induction on j. (1) is purely a finrank inequality; (2) carries
-- the dependent recursion + induction-on-j proof obligation.
import Mathlib
import Problems.LinearAlgebra.schur_triangularization.Defs
import Problems.LinearAlgebra.schur_triangularization.proofs._strategy_s10841

namespace Problems.LinearAlgebra.schur_triangularization

def flag_vector_seq_exists := @Problems.LinearAlgebra.schur_triangularization.s10841

end Problems.LinearAlgebra.schur_triangularization
