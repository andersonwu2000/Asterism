-- Pullback of a flat `k`-form along a smooth map `e`, read in coordinates, is smooth.
-- Three pieces combined: (1) `φ ∘ e` smooth = `hφ.comp he`; (2) `x ↦ fderiv ℝ e x` smooth
-- = `he.fderiv_right (∞+1 ≤ ∞)`; (3) the joint fibrewise composition
-- `(w, L) ↦ w.compContinuousLinearMap L` is smooth — the genuine gap above the boundary
-- case, since it is linear in `w` but degree-`k` in `L`. Piece (3) is the ℝ-only Library
-- crux `contdiff_comp_continuous_linear_map_clm` (proved via alternatization, dividing by
-- `(card ι)!`, hence characteristic-zero / ℝ-only): `g ↦ compContinuousLinearMapCLM g` is
-- `C^n`. Assemble by `ContDiff.clm_apply` against pieces (1),(2), rewriting
-- `compContinuousLinearMapCLM_apply` so the CLM-valued arg lands on the varying `L`.
import Mathlib
import Problems.Geometry.pullback_flat_smooth.Defs
import Problems.Geometry.pullback_flat_smooth.proofs._strategy_s17794

namespace Problems.Geometry.pullback_flat_smooth

def main := @Problems.Geometry.pullback_flat_smooth.s17794

end Problems.Geometry.pullback_flat_smooth
