import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- entry_kind: Builder
-- xpow_modbymonic_self: X^(natDegree f) %ₘ f = X^(natDegree f) - f for monic f,
-- via div_modByMonic_unique with quotient 1 and remainder X^n - f.
theorem xpow_modbymonic_self {K : Type*} [Field K] {f : Polynomial K} (hf : f.Monic) :
    Polynomial.X ^ f.natDegree %ₘ f = Polynomial.X ^ f.natDegree - f := by
  have hfdeg : f.degree = f.natDegree := Polynomial.degree_eq_natDegree hf.ne_zero
  have hdeg : (Polynomial.X (R := K) ^ f.natDegree).degree = f.degree := by
    rw [Polynomial.degree_X_pow, hfdeg]
  have hlc : (Polynomial.X (R := K) ^ f.natDegree).leadingCoeff = f.leadingCoeff := by
    rw [Polynomial.leadingCoeff_X_pow, hf.leadingCoeff]
  exact (Polynomial.div_modByMonic_unique 1 (Polynomial.X ^ f.natDegree - f) hf
    ⟨by ring, hdeg ▸ Polynomial.degree_sub_lt hdeg
        (pow_ne_zero f.natDegree (Polynomial.X_ne_zero (R := K))) hlc⟩).2



end Problems.LinearAlgebra.rational_canonical_form
