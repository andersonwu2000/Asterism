-- Drop φ entirely: an orbit section exists for ANY group action.
-- `MulAction.compHom E φ` makes `FreeGroup (Fin 2)` act on `E` by `w • x = φ w • x`
-- (definitionally), so the abstract `orbit_section_general` (rep + word with
-- `wrd x • rep x = x` and `rep` constant on each orbit) specializes directly:
-- the two conjuncts close by `exact h1`/`exact h2` since compHom's `•` is defeq to `φ _ •`.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11483

namespace Problems.Geometry.banach_tarski

def orbit_section_exists := @Problems.Geometry.banach_tarski.s11483

end Problems.Geometry.banach_tarski
