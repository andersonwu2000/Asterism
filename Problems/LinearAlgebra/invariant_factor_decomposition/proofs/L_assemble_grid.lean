-- Direct assembly of the per-column sorting data into the global grid; no
-- sub-goals, the sorting is already supplied as hypotheses so only plumbing
-- remains.  Witness: r' := r, c i t := cvec t i, idx i := (pos (key i) ⟨i,rfl⟩, key i).
--   • monotonicity ← hmono;  key-match ← rfl;  value-match ← hval.
--   • no-empty-row ← hcover places an element in each row, hval+hw make it > 0.
--   • injectivity: the dependent `{j // key j = t}`-subtype transport is sidestepped
--     by factoring `idx` through the sigma column `Σ t, {j // key j = t}` — the map
--     `(pos p.1 p.2, p.1)` is injective (snd pins the column, then subst + hinj), and
--     `idx = · ∘ (i ↦ ⟨key i, ⟨i,rfl⟩⟩)` with the latter trivially injective.
--   • zero-padding: same column-transport handled by `subst hjv` before invoking hpad.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11587

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def assemble_grid := @Problems.LinearAlgebra.invariant_factor_decomposition.s11587

end Problems.LinearAlgebra.invariant_factor_decomposition
