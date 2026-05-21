-- Two-step FTC: (1) `right_integrand_cont_on_icc` — `2 · derivWithin β' (Icc 0 1) (2·s-1)`
-- is continuous on `Icc (1/2) 1` from `ContDiffOn ℝ 1 β'`.
-- (2) `ftc_const_add_right_half` — abstract FTC: for any continuous `g` on `Icc (1/2) 1`
-- and any constant `C`, `fun u => C + ∫ s in (1/2)..u, g s` has derivative `g(t)` at
-- every `t ∈ Ioo (1/2) 1`. Specialise to `g := 2 · derivWithin β' (Icc 0 1) (2·s-1)`
-- and `C := α' 0 + ∫ s in 0..(1/2), 2 · derivWithin α' (Icc 0 1) (2·s)`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10683

namespace Problems.residue_thm

def right_split_has_deriv_at_on_ioo := @Problems.residue_thm.s10683

end Problems.residue_thm
