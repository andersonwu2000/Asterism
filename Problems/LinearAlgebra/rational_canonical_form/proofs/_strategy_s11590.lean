import Mathlib
import Problems.LinearAlgebra.rational_canonical_form.Defs
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_xpow_modbymonic_lt
import Problems.LinearAlgebra.rational_canonical_form.proofs.L_xpow_modbymonic_self

namespace Problems.LinearAlgebra.rational_canonical_form

-- Entrywise computation of `(X^(j+1) %ₘ f).coeff i`, split on whether the
-- exponent `j+1` is below `natDegree f` (low) or equals it (high).
-- Low: `X^(j+1) %ₘ f = X^(j+1)` (xpow_modbymonic_lt), coeff is `if i = j+1`.
-- High: `X^n %ₘ f = X^n - f` (xpow_modbymonic_self); coeff i = -f.coeff i.
-- Both reduce to `companionMatrix` via its definition + Fin bounds (omega).
theorem s11590 {K : Type*} [Field K] {f : Polynomial K}
    (hf : f.Monic) (i j : Fin f.natDegree) :
    (Polynomial.X ^ ((j : ℕ) + 1) %ₘ f).coeff i = companionMatrix f i j  := by
  by_cases hj : (j : ℕ) + 1 < f.natDegree
  · -- low case
    have hlt : Polynomial.X ^ ((j : ℕ) + 1) %ₘ f = Polynomial.X ^ ((j : ℕ) + 1) :=
      xpow_modbymonic_lt hf hj
    have hjn : (j : ℕ) ≠ f.natDegree - 1 := by omega
    rw [hlt, Polynomial.coeff_X_pow, companionMatrix]
    simp only [Matrix.of_apply]
    rw [if_neg hjn]
  · -- high case
    have hjeq : (j : ℕ) + 1 = f.natDegree := by have := j.is_lt; omega
    have hself : Polynomial.X ^ ((j : ℕ) + 1) %ₘ f
        = Polynomial.X ^ ((j : ℕ) + 1) - f := by
      rw [hjeq]; exact xpow_modbymonic_self hf
    have hjn : (j : ℕ) = f.natDegree - 1 := by omega
    have hin : (i : ℕ) ≠ (j : ℕ) + 1 := by have := i.is_lt; omega
    rw [hself, Polynomial.coeff_sub, Polynomial.coeff_X_pow, companionMatrix]
    simp only [Matrix.of_apply]
    rw [if_neg hin, if_neg hin, if_pos hjn]
    ring

end Problems.LinearAlgebra.rational_canonical_form
