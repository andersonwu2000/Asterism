-- Obtain the invariant factors `f` + the K[X]-linear iso `e` to the cyclic direct
-- sum from the Library (Manifest steps 0-1), then delegate the K-basis + companion
-- block-diagonal matrix assembly (steps 2-3) to `companion_block_basis`, which takes
-- `e` as a hypothesis so the PID/CRT existence work is already discharged.
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11591

namespace Problems.LinearAlgebra.rational_canonical_form

def main := @Problems.LinearAlgebra.rational_canonical_form.s11591

end Problems.LinearAlgebra.rational_canonical_form
