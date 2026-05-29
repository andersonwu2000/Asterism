-- φ-images of the 5 FreeGroup pieces cover φ.range.
-- key: φ '' distributes over the indexed union (cases on Option, defeq per branch).
-- h_cover: `Set.iUnion_option` splits the Option-union into the empty-word piece ∪
--   the head-letter pieces; the match-free `freegroup_cover` (lone sub-goal) gives = univ.
-- Then φ '' univ = Set.range φ = ↑φ.range. The sub-goal is stated WITHOUT a `match`
--   (explicit ∪ / ⋃ p) so it carries no anonymous match-aux constant — avoids the
--   cross-file `match` defeq mismatch that an Option-match restatement would trigger.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11415

namespace Problems.Geometry.banach_tarski

def image_pieces_cover_range := @Problems.Geometry.banach_tarski.s11415

end Problems.Geometry.banach_tarski
