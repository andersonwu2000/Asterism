-- Split assembly (basis transport) from per-block companion identification.
-- `block_assembly` builds the K-basis (DFinsupp of per-block power bases, transported
--   through `e` and `Module.AEval'.of T`) and shows `toMatrix b b T` is the block diagonal
--   of the per-block "multiply by root" operator matrices — pure functorial transport, no
--   polynomial arithmetic.
-- `block_companion` identifies each per-block operator matrix with `companionMatrix (f i)`
--   (the %ₘ-coefficient computation), so the two pieces are strictly simpler than the parent.
-- Combine: rewrite by `block_assembly`, then `congr`/`funext` and discharge each block by
--   `block_companion`.
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11592

namespace Problems.LinearAlgebra.rational_canonical_form

def companion_block_basis := @Problems.LinearAlgebra.rational_canonical_form.s11592

end Problems.LinearAlgebra.rational_canonical_form
