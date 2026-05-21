-- Reduce the a.e. bound on `uIoc 0 1` to the pointwise interior bound on `Ioo 0 1 × Ioo 0 1`.
-- The complement `uIoc 0 1 \ Ioo 0 1 = {1}` is null, so the strong sub-goal closes the a.e. one
-- after filter_upwards on `t ≠ 1`. Defers all analytic content (C² bounds on H, f, f') to the
-- interior-only sub-goal where `Icc 0 1 ∈ 𝓝 x` and `Icc 0 1 ∈ 𝓝 t` unlock the derivative formula.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10337

namespace Problems.residue_thm

def homotopy_partial_tau_uniform_bound := @Problems.residue_thm.s10337

end Problems.residue_thm
