import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs

namespace Problems.LinearAlgebra.rational_canonical_form

-- xpow_modbymonic_lt: X^m %ₘ f = X^m when m < natDegree f (monic f),
-- via modByMonic_eq_self_iff + degree_X_pow + degree_eq_natDegree.
theorem xpow_modbymonic_lt {K : Type*} [Field K] {f : Polynomial K} (hf : f.Monic)
    {m : ℕ} (hm : m < f.natDegree) :
    Polynomial.X ^ m %ₘ f = Polynomial.X ^ m := by
  rw [Polynomial.modByMonic_eq_self_iff hf]
  rw [Polynomial.degree_X_pow]
  rw [Polynomial.degree_eq_natDegree hf.ne_zero]; exact_mod_cast hm

end Problems.LinearAlgebra.rational_canonical_form
