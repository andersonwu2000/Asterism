-- Reduce change-of-variables wrapper into (1) integrand equality on the
-- left half via the chain rule h(t) = α'(2t), and (2) a pure t ↦ 2t
-- substitution rewriting ∫₀^{1/2} 2·Q(α'(2t))·α''(2t) dt as ∫₀^1 Q(α'·)·α'' du.
-- Sub-goal (1) carries `hh`, `hh_left` to perform `deriv` chain rule; sub-goal
-- (2) is `α'`-only (no `h`), strictly simpler than the parent.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10678

namespace Problems.residue_thm

def subst_alpha_step_wrapper := @Problems.residue_thm.s10678

end Problems.residue_thm
