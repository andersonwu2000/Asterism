import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- pow_p_sub_one_eq_one: Fermat's little theorem — (2:ZMod p)^(p-1)=1 since p≥5 prime implies p∤2
theorem pow_p_sub_one_eq_one :
    ∀ (m : ℕ), 2 ≤ m → m ^ 2 ∣ 2 ^ m + 1 → 3 ∣ m → ¬ (9 ∣ m) → ¬ (7 ∣ m) →
      ∀ p, Nat.Prime p → 5 ≤ p → p ∣ m → (2 : ZMod p) ^ (p - 1) = 1 := by
  intro m hm2 hdvd h3 h9 h7 p hp h5 hpdvd
  haveI : Fact p.Prime := ⟨hp⟩
  apply ZMod.pow_card_sub_one_eq_one
  have h2ne : (2 : ZMod p) ≠ 0 := by
    intro h
    have hcast : ((2 : ℕ) : ZMod p) = 0 := by exact_mod_cast h
    rw [CharP.cast_eq_zero_iff (ZMod p) p] at hcast
    have := Nat.le_of_dvd (by norm_num) hcast
    linarith
  exact h2ne

end Problems.Minif2f.imo_1990_p3
