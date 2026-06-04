import Mathlib
import Problems.Minif2f.amc12b_2002_p3.Defs
import Problems.Minif2f.amc12b_2002_p3.proofs.L_subset_singleton_three
import Problems.Minif2f.amc12b_2002_p3.proofs.L_three_in_s

namespace Problems.Minif2f.amc12b_2002_p3

-- Split S.card = 1 into two leaf claims: (3 : ℕ) ∈ S, and S ⊆ {3}.
-- Antisymm gives S = {3}; Finset.card_singleton closes. Each sub-goal is strictly
-- simpler: three_in_s reduces to checking 3^2+2-3*3=2 is prime; subset_singleton_three
-- bounds membership by ruling out n=0,1,2 and showing (n-1)(n-2) is composite for n≥4.
theorem s9379 : ∀ (S : Finset ℕ) -- note, we use (n^2 + 2 - 3 * n) over (n^2 - 3 * n + 2) because nat subtraction truncates the latter at 1 and 2 (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ Nat.Prime (n ^ 2 + 2 - 3 * n)) : S.card = 1 := by sorry
    (h₀ : ∀ n : ℕ, n ∈ S ↔ 0 < n ∧ Nat.Prime (n ^ 2 + 2 - 3 * n)), S.card = 1 :=
  fun S h₀ =>
    let h_in : (3 : ℕ) ∈ S := three_in_s S h₀
    let h_sub : S ⊆ ({3} : Finset ℕ) := subset_singleton_three S h₀
    let hS : S = ({3} : Finset ℕ) :=
      Finset.Subset.antisymm h_sub (Finset.singleton_subset_iff.mpr h_in)
    hS ▸ Finset.card_singleton 3

end Problems.Minif2f.amc12b_2002_p3
