-- Skolemize: pick basepoint z₀ = a + 1, and use Classical.choose over the
-- "every z ≠ a has a C¹ path from a+1 avoiding a" existence claim to construct ψ.
-- Sub-goal `path_to_basepoint_avoiding` carries the C¹-path-connectedness of ℂ \ {a}.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10505

namespace Problems.residue_thm

def path_chooser_avoiding_singularity := @Problems.residue_thm.s10505

end Problems.residue_thm
