import Mathlib
import Problems.LinearAlgebra.primary_decomposition.Defs

namespace Problems.LinearAlgebra.primary_decomposition

-- entry_kind: Builder
-- ker_aeval_le_of_dvd: kernel inclusion under polynomial divisibility
-- p ∣ r means r = q*p for some q; aeval T r = aeval T q ∘ aeval T p,
-- so any v annihilated by aeval T p is annihilated by aeval T r.
theorem ker_aeval_le_of_dvd
    {K V : Type*} [Field K] [AddCommGroup V] [Module K V]
    (T : V →ₗ[K] V) (p r : Polynomial K) (h : p ∣ r) :
    LinearMap.ker (Polynomial.aeval T p) ≤ LinearMap.ker (Polynomial.aeval T r) := by
  intro v hv
  simp only [LinearMap.mem_ker] at *
  obtain ⟨q, hq⟩ := h
  rw [hq, mul_comm, map_mul, Module.End.mul_apply, hv, map_zero]

end Problems.LinearAlgebra.primary_decomposition