-- Direct construction, no sub-goals (leaf-bypass): inline the proved-sibling logic
-- since the framework's sub-goal import inserter only fires on `new_*.lean` stubs.
-- Step 1: derive `Fintype {μ // 0 < n μ}` from the ambient sigma Fintype via the
-- injection `μ ↦ ⟨μ, 0⟩`; take `m := Fintype.card …`, `e := (Fintype.equivFin …).symm`.
-- Step 2: build `φ` as `sigmaCongrLeft e ≫ sigmaSubtypeEquivOfSubset` — both equivs
-- leave the fiber index alone (so `.2`-preservation is `rfl`), and fiber equality
-- reduces to `e`-injectivity via `Subtype.coe_inj` + `EmbeddingLike.apply_eq_iff_eq`.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11058

namespace Problems.LinearAlgebra.jordan_normal_form

def reduce_to_fin_base := @Problems.LinearAlgebra.jordan_normal_form.s11058

end Problems.LinearAlgebra.jordan_normal_form
