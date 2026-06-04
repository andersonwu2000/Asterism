-- Decompose the keyed-exponent grid into a per-column sorting lemma and a
-- column-assembly lemma, both abstract over the index type.
--   `column_block` (sub-goal): for any `Fintype J` with weight `w` and a height
--     `r ≥ #J`, sort one column's weights into a monotone, bottom-aligned vector
--     `cvec : Fin r → ℕ` with an injective placement `pos : J → Fin r`, zero
--     padding above the image, and the bottom block `[r - #J, r)` fully filled.
--   `assemble_grid` (sub-goal): given each column's solved `cvec`/`pos` plus a
--     row-coverage hypothesis, glue them into the global grid and discharge all
--     six conjuncts (monotonicity, injectivity, key/value match, no-empty-row,
--     zero-padding) — the sorting is now hypotheses, so only plumbing remains.
-- The combinator picks `r := ⨆ₜ #(column t)`, applies `column_block` fibrewise
-- via `choose`, derives row-coverage `hcover` from the height-achieving column
-- (`Finset.exists_mem_eq_sup` + the bottom-fill guarantee), then hands the
-- per-column data to `assemble_grid`.  Each sub-goal is strictly simpler: the
-- construction (sorting) lives in `column_block`, the bookkeeping in
-- `assemble_grid`, and both drop the parent's `e`-subtype coupling.
import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs._strategy_s11585

namespace Problems.LinearAlgebra.invariant_factor_decomposition

def monotone_grid_of_keyed_exponents := @Problems.LinearAlgebra.invariant_factor_decomposition.s11585

end Problems.LinearAlgebra.invariant_factor_decomposition
