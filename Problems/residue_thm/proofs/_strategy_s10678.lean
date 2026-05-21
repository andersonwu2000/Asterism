import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_int_two_alpha_eq_alpha
import Problems.residue_thm.proofs.L_subst_alpha_chain_rule_left

namespace Problems.residue_thm

-- Reduce change-of-variables wrapper into (1) integrand equality on the
-- left half via the chain rule h(t) = α'(2t), and (2) a pure t ↦ 2t
-- substitution rewriting ∫₀^{1/2} 2·Q(α'(2t))·α''(2t) dt as ∫₀^1 Q(α'·)·α'' du.
-- Sub-goal (1) carries `hh`, `hh_left` to perform `deriv` chain rule; sub-goal
-- (2) is `α'`-only (no `h`), strictly simpler than the parent.
theorem s10678
    {Q : ℂ → ℂ} {α' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1/2), h t = α' (2*t)) :
    (∫ t in (0:ℝ)..(1/2:ℝ), Q (h t) * deriv h t) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t)  := by
  have h1 := subst_alpha_chain_rule_left (Q := Q) hα' hh hh_left
  have h2 := int_two_alpha_eq_alpha (Q := Q) (h := h) hα' hh hh_left
  exact h1.trans h2

end Problems.residue_thm
