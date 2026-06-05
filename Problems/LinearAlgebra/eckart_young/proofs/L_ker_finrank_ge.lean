import Mathlib
import Problems.LinearAlgebra.eckart_young.Defs

namespace Problems.LinearAlgebra.eckart_young

-- ker_finrank_ge: rank–nullity bounds finrank E by finrank (ker S) + k when range S has rank ≤ k
theorem ker_finrank_ge {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (S : E →ₗ[𝕜] F) (k : ℕ)
    (hrank : Module.finrank 𝕜 (LinearMap.range S) ≤ k) :
    Module.finrank 𝕜 E ≤ Module.finrank 𝕜 (LinearMap.ker S) + k := by
  have h := S.finrank_range_add_finrank_ker (K := 𝕜)
  omega

end Problems.LinearAlgebra.eckart_young
