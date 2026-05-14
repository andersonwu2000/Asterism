import Mathlib

/-!
Problem-level shared definitions for `sl2_v_n_irreducible`.

The theorem references Mathlib's `IsSl2Triple` and
`IsSl2Triple.HasPrimitiveVectorWith` machinery directly
(`Mathlib.Algebra.Lie.Sl2`, Oliver Nash 2024). No problem-specific
definitions are needed — the open clauses below bring the LieAlgebra
and Module namespaces into scope so the statement and proofs read
without qualification.
-/

open LieAlgebra LieModule Module IsSl2Triple

namespace Problems.sl2_v_n_irreducible

end Problems.sl2_v_n_irreducible
