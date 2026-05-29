-- Lift F₂'s 5-piece paradoxical split through the injective hom φ.
-- Conjuncts 3,4 (`tr i`) are proved INLINE here — each generator-translate is a
--   direct instance of the proved `range_translate_eq_range_sdiff_of_injective`
--   (s11412) fed by `translate_starts_eq_compl i` (rewritten compl→univ∖); this
--   keeps the FreeGroup-flavoured translate identity out of a Builder.
-- h_disj/h_cover: the φ-images of the empty-word piece + 4 head-letter pieces stay
--   pairwise-disjoint / cover φ.range (injectivity transports both) — the only two
--   structurally-bigger sub-goals.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11413

namespace Problems.Geometry.banach_tarski

def rotation_subgroup_paradoxical := @Problems.Geometry.banach_tarski.s11413

end Problems.Geometry.banach_tarski
