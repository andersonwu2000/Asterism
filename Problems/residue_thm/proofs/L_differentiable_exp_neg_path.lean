-- Split the product `exp(-G(s)) · (γ s - a)` into its two factors and combine via `.mul`.
-- Sub-goals: (1) differentiability of `s ↦ exp(-∫₀ˢ deriv γ /(γ-a))` — analytic core,
-- needs FTC + chain rule; (2) differentiability of `s ↦ γ s - a` — direct from `hγ`.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10303

namespace Problems.residue_thm

def differentiable_exp_neg_path := @Problems.residue_thm.s10303

end Problems.residue_thm
