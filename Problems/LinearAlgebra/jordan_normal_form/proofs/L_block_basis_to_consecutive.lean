-- Reindex via block_enum_consecutive + cardinality bridge.
-- block_enum_consecutive (proved brick s10915) gives e : Fin (∑ k s) ≃ Σ s, Fin (k s).
-- finrank K W = ∑ k s from basis c; finCongr then closes Fin (finrank W) ≃ Fin (∑ k s).
-- Compose: φ := finCongr.trans e gives Fin (finrank W) ≃ Σ s, Fin (k s); reindex c via φ.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11023

namespace Problems.LinearAlgebra.jordan_normal_form

def block_basis_to_consecutive := @Problems.LinearAlgebra.jordan_normal_form.s11023

end Problems.LinearAlgebra.jordan_normal_form
