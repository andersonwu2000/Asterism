-- Reduce the operator-norm bound to a pointwise bound via ContinuousAlternatingMap.opNorm_le_bound.
-- alternatization m v = ∑ σ : Perm ι, sign σ • m (v ∘ σ) (alternatization_apply_apply), so the
-- pointwise value is a sum of (card ι)! terms each bounded by ‖m‖ * ∏ ‖v i‖: sub-goal
-- alternatization_term_norm_le bounds one sign-permuted term (sign is a unit, prod reindexes by σ);
-- sub-goal alternatization_pointwise_norm_le assembles the sum (norm_sum_le + Fintype.card_perm).
import Mathlib
import Problems.Geometry.stokes_form_bundle.Defs
import Problems.Geometry.stokes_form_bundle.proofs._strategy_s11683

namespace Problems.Geometry.stokes_form_bundle

def alternatization_norm_le := @Problems.Geometry.stokes_form_bundle.s11683

end Problems.Geometry.stokes_form_bundle
