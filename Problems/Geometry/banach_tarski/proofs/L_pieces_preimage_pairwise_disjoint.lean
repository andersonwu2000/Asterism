-- Direct leaf: the 5-piece base disjointness is pairwise-distinct head-key separation.
-- After `Set.disjoint_left`, case-split both indices: a word in the empty-word piece
-- (`toWord = []`) has `head? = none`, contradicting any `head? = some p`; two `some`
-- pieces with distinct keys contradict equal `head?`. `simp_all` + `toWord_one` closes all.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11416

namespace Problems.Geometry.banach_tarski

def pieces_preimage_pairwise_disjoint := @Problems.Geometry.banach_tarski.s11416

end Problems.Geometry.banach_tarski
