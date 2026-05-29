-- Direct proof: push the translate identity `a • W = univ \ V` through φ.
-- h2: injective image preserves set-difference (`Set.image_diff hφ`) and
--     `φ '' univ = φ.range` (`Set.image_univ` + `MonoidHom.coe_range`).
-- h1: image of a left-translate is the translate of the image, element-wise
--     via `map_mul` (no dedicated mathlib lemma `Set.image_smul_set` exists).
-- Then rewrite `φ '' (a • W) = φ '' (univ \ V)` by both to land on the goal.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11412

namespace Problems.Geometry.banach_tarski

def range_translate_eq_range_sdiff_of_injective := @Problems.Geometry.banach_tarski.s11412

end Problems.Geometry.banach_tarski
