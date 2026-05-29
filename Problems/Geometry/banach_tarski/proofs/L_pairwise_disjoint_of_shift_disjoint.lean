-- Direct: `wlog i < j` (Disjoint is symmetric), set n = j - i ≥ 1, then
-- (g^j) '' D = (g^i) '' ((g^n) '' D) via pow_add + image_comp; cancel the injective g^i
-- (Set.disjoint_image_iff) to land on `(h n).symm : Disjoint D ((g^n) '' D)`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11430

namespace Problems.Geometry.banach_tarski

def pairwise_disjoint_of_shift_disjoint := @Problems.Geometry.banach_tarski.s11430

end Problems.Geometry.banach_tarski
