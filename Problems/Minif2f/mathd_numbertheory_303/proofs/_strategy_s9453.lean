import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs
import Problems.Minif2f.mathd_numbertheory_303.proofs.L_dvd_91_ge_2_in_set
import Problems.Minif2f.mathd_numbertheory_303.proofs.L_modeq_imp_dvd_91

namespace Problems.Minif2f.mathd_numbertheory_303

-- Split into: (1) modEq encodes divisibility of 91; (2) divisors of 91 with n≥2 enumerate to {7,13,91}.
-- Sub-goal 1 (modeq_imp_dvd_91): `171 ≡ 80 [MOD n] → n ∣ 91` via `Nat.modEq_iff_dvd'`.
-- Sub-goal 2 (dvd_91_ge_2_in_set): `n ∣ 91 → 2 ≤ n → n ∈ {7,13,91}` via bound + interval_cases.
-- 468 ≡ 13 hypothesis is redundant (it gives n ∣ 455 = 5·91, weaker than n ∣ 91).
theorem s9453 :
    ∀ n : ℕ, (2 ≤ n ∧ 171 ≡ 80 [MOD n] ∧ 468 ≡ 13 [MOD n]) →
      (n = 7 ∨ n = 13 ∨ n = 91)  := by
  intro n ⟨h2, h171, _h468⟩
  have hd : n ∣ 91 := modeq_imp_dvd_91 n h171
  exact dvd_91_ge_2_in_set n hd h2

end Problems.Minif2f.mathd_numbertheory_303
