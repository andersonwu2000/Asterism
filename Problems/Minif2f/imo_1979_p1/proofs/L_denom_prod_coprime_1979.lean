import Mathlib
import Problems.Minif2f.imo_1979_p1.Defs

namespace Problems.Minif2f.imo_1979_p1

-- denom_prod_coprime_1979: product of factors in [660,1319] is coprime to prime 1979
-- Each factor (660+j) and (1319-j) lies in [660,1319] ⊂ (0,1979), so 1979∤each factor,
-- and a prime p is coprime to n iff p∤n; coprimality distributes over products.
theorem denom_prod_coprime_1979 :
    Nat.Coprime (∏ j ∈ Finset.range 330, ((660 + j) * (1319 - j))) 1979 := by
  apply Nat.Coprime.prod_left
  intro j hj
  simp [Finset.mem_range] at hj
  apply Nat.Coprime.mul_left
  all_goals (
    apply Nat.Coprime.symm
    apply (Nat.Prime.coprime_iff_not_dvd (by norm_num : Nat.Prime 1979)).mpr
    intro hdvd
    have := Nat.le_of_dvd (by omega) hdvd
    omega)

end Problems.Minif2f.imo_1979_p1
