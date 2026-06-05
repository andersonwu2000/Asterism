-- Membership direction of Eckart–Young: build a rank-≤k truncation `S` whose
-- residual is pointwise bounded by σ_k.  Factor `S = T ∘ₗ P` through a rank-≤k
-- projection `P : E →ₗ E` (sub-goal `exists_truncation_projection`, the SVD/
-- spectral content).  Then `range (T∘ₗP) = T.map (range P)` has finrank ≤
-- finrank (range P) ≤ k (`Submodule.finrank_map_le`), and `(T-S) x = T x - T(Px)`
-- (`LinearMap.sub_apply`/`comp_apply`) inherits the pointwise bound directly.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11652

namespace Problems.LinearAlgebra.eckart_young

def exists_truncation_pointwise_le_singularvalue := @Problems.LinearAlgebra.eckart_young.s11652

end Problems.LinearAlgebra.eckart_young
