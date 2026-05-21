-- Bypass the `deriv` (not `derivWithin`) endpoint-junk trap on `[0, 1/2]`: prove the
-- integrand with `derivWithin γ (Icc 0 1)` is `ContinuousOn (Icc 0 (1/2))` (sub-goal),
-- upgrade to `IntervalIntegrable` via `ContinuousOn.intervalIntegrable_of_Icc`, then
-- swap `derivWithin γ (Icc 0 1) ↔ deriv γ` a.e. on `Ι 0 (1/2)` via `derivWithin_of_mem_nhds`
-- (`Icc 0 1 ∈ 𝓝 t` for any `t ∈ Ioo 0 (1/2) ⊆ Ioo 0 1`).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10672

namespace Problems.residue_thm

def flat_ftc_intintegrable_left_half := @Problems.residue_thm.s10672

end Problems.residue_thm
