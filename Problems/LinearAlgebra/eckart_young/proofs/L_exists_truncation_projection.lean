-- Eckart–Young membership (SVD content): build the rank-≤k truncation projection `P`.
-- Split on `k < finrank E`.  Degenerate branch (`finrank E ≤ k`): `P = id`, zero residual.
-- Main branch: take `K` = span of the top-k right singular vectors (eigenvectors of `T†T`),
-- and `P = K.starProjection`.  Two sub-goals factor the content:
--   • `bottom_span_norm_le` — `T` shrinks `Kᗮ` by `σ_k` (the spectral/SVD bound);
--   • `norm_sub_starprojection_le` — the orthogonal projection is norm non-increasing.
-- finrank(range P) = finrank K ≤ k via `range_starProjection` + `finrank_range_le_card`;
-- `(T-S)x = T(x - Px)` with `x - Px ∈ Kᗮ` chains the two bounds with the contraction.
import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs
import Problems.LinearAlgebra.eckart_young.proofs._strategy_s11654

namespace Problems.LinearAlgebra.eckart_young

def exists_truncation_projection := @Problems.LinearAlgebra.eckart_young.s11654

end Problems.LinearAlgebra.eckart_young
