-- Radius-independence of `∮ w in C(z₀, r), f w / (w - z')` reduces to Mathlib's
-- `circleIntegral_eq_of_differentiable_on_annulus_off_countable` after WLOG `r₁ ≤ r₂`.
-- Two sub-goals supply the annulus-side hypotheses of that lemma for the Cauchy kernel
-- `w ↦ f w / (w - z')`: continuity on the closed annulus, and differentiability at each
-- point of the open annulus. Both isolate the "kernel has no pole inside the annulus"
-- analytic reasoning into Builder leaves and keep the patch as pure case-dispatch.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10422

namespace Problems.residue_thm

def cauchy_kernel_circle_int_radius_indep := @Problems.residue_thm.s10422

end Problems.residue_thm
