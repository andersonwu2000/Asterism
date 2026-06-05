import Mathlib
import Problems.LinearAlgebra.sylvester_criterion.Defs
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_empty
import Problems.LinearAlgebra.sylvester_criterion.proofs.L_posdef_succ_step

namespace Problems.LinearAlgebra.sylvester_criterion

-- Sylvester reverse direction: induction on the dimension n (revert M first so the
-- inductive hypothesis quantifies over every n×n matrix).
--  • base `posdef_empty`: the 0×0 matrix is PosDef vacuously.
--  • step `posdef_succ_step`: given ih (the criterion for n) plus the (n+1) leading
--    minors, the Schur-complement argument upgrades to PosDef.
-- `induction` is the combinator; each branch is strictly simpler (base trivial; step
-- has ih in hand, so it no longer carries the induction setup).
theorem s11603 {n : ℕ} (M : Matrix (Fin n) (Fin n) ℝ) :
    M.IsHermitian → (∀ k : Fin n, 0 < leadingPrincipalMinor M k) → M.PosDef  := by
  revert M
  induction n with
  | zero =>
    intro M hHerm _
    exact posdef_empty M hHerm
  | succ n ih =>
    intro M hHerm hMinors
    exact posdef_succ_step ih M hHerm hMinors

end Problems.LinearAlgebra.sylvester_criterion
