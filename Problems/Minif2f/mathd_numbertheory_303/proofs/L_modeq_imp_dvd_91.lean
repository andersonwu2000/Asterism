import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs

namespace Problems.Minif2f.mathd_numbertheory_303

-- modeq_imp_dvd_91: 171 ≡ 80 [MOD n] encodes n ∣ 91 via Nat.modEq_iff_dvd' (171 - 80 = 91)
-- h.symm flips to 80 ≡ 171 [MOD n] which matches the iff's expected form
theorem modeq_imp_dvd_91 : ∀ n : ℕ, 171 ≡ 80 [MOD n] → n ∣ 91 := by
  intro n h
  have hdvd : n ∣ 171 - 80 := (Nat.modEq_iff_dvd' (by norm_num : 80 ≤ 171)).mp h.symm
  simpa using hdvd

end Problems.Minif2f.mathd_numbertheory_303
