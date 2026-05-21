import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_reparam_flat_endpoints_step_wrapper

namespace Problems.residue_thm

-- Single-step alias: this goal has the exact signature of the proved sibling
-- `c1_path_smooth_reparam_flat_endpoints` (s10579). Per the wrapper-import
-- lesson, citing a proved sibling directly from `_strategy_*.lean` fails the
-- auto-import — route through a Builder sub-goal whose `L_*.lean` will
-- inherit the proved-sibling import for free.
theorem s10674
    {Q : ℂ → ℂ} {a : ℂ} {γ : ℝ → ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∃ γ' : ℝ → ℂ,
      ContDiffOn ℝ 1 γ' (Set.Icc 0 1) ∧
      γ' 0 = γ 0 ∧
      γ' 1 = γ 1 ∧
      derivWithin γ' (Set.Icc 0 1) 0 = 0 ∧
      derivWithin γ' (Set.Icc 0 1) 1 = 0 ∧
      (∀ t ∈ Set.Icc (0 : ℝ) 1, γ' t ≠ a) ∧
      (∫ t in (0 : ℝ)..1, Q (γ' t) * deriv γ' t) =
        (∫ t in (0 : ℝ)..1, Q (γ t) * deriv γ t)  := by
  exact reparam_flat_endpoints_step_wrapper (Q := Q) hγ havoid

end Problems.residue_thm
