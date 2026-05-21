-- Compose two siblings: (A) `uniform_ball_thickening_of_path` yields a single
-- positive radius δ with `ball (γ t) δ ⊆ U` uniformly in t (compactness +
-- Lebesgue-number on the open cover of γ([0,1])); (B) `partition_subdivides_path_in_ball`
-- partitions [0,1] so each subarc lands in `ball (γ (tᵢ)) δ`. Centers
-- `c i := γ (t i)`, radii `r i := δ` package the cover required by the parent.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10496

namespace Problems.residue_thm

def ball_cover_along_path_exists := @Problems.residue_thm.s10496

end Problems.residue_thm
