-- Sylvester's criterion: split the iff into its two implications.
-- Forward (`minors_pos_of_posdef`): each leading block is a PosDef submatrix, so its
-- determinant (= the leading minor) is positive — short, no induction.
-- Reverse (`posdef_of_minors_pos`): induction on n via Schur complement, upgrading
-- PosSemidef to PosDef using the proved sibling. Iff.intro recombines them.
import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs._strategy_s11602

namespace Problems.LinearAlgebra.sylvester_criterion

def main := @Problems.LinearAlgebra.sylvester_criterion.s11602

end Problems.LinearAlgebra.sylvester_criterion
