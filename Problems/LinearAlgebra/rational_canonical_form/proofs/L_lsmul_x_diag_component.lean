-- Diagonal component of the `X`-action: peel the `lsmul`/`restrictScalars`/`DirectSum.smul`
-- wrappers (`restrictScalars_apply`, `lsmul_apply`, `DirectSum.smul_apply` pinned to the
-- `Submodule.span` fiber family), reducing the goal to `X • eⱼₗ-component = root fⱼ * basis l`.
-- The `X`-smul (on `K[X] ⧸ Submodule.span {fⱼ}`) is defeq to `root fⱼ * ·` (the `AdjoinRoot`
-- multiplication), so `change` rephrases the LHS as `root fⱼ * component` and `congrArg`
-- transports the single remaining fact:
--   `dfinsupp_basis_diag_component` — the `j`-th component of `DFinsupp.basis pb ⟨j,l⟩` is
--   `pb j l`. That sub-goal is a pure `DFinsupp.basis` evaluation (no `X`-action, no quotient
--   seam) — strictly simpler than the parent. The `X•·`/`root*·` instance bridge stays inline
--   here (it is unstatable as a standalone single-variable lemma).
import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs._strategy_s11598

namespace Problems.LinearAlgebra.rational_canonical_form

def lsmul_x_diag_component := @Problems.LinearAlgebra.rational_canonical_form.s11598

end Problems.LinearAlgebra.rational_canonical_form
