import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs

namespace Problems.Minif2f.mathd_numbertheory_221

-- prod_three_primefactors_singleton: product-3 forces primeFactors to be a singleton;
-- if the set were empty, the empty product = 1 ≠ 3; if it had ≥ 2 elements, each
-- factor (factorization p + 1) ≥ 2, so the product ≥ 4 > 3.
theorem prod_three_primefactors_singleton :
    ∀ y : ℕ, y ≠ 0 →
      (∏ p ∈ y.primeFactors, (y.factorization p + 1)) = 3 →
      ∃ p : ℕ, p.Prime ∧ y.primeFactors = {p} := by
  intro y hy hprod
  have hnonempty : y.primeFactors.Nonempty := by
    by_contra h
    rw [Finset.not_nonempty_iff_eq_empty] at h
    simp [h] at hprod
  have hcard_one : y.primeFactors.card = 1 := by
    by_contra hcard
    have hlt : 1 < y.primeFactors.card := by
      have := Finset.card_pos.mpr hnonempty; omega
    obtain ⟨a, ha, b, hb, hab⟩ := Finset.one_lt_card.mp hlt
    have ha_pos : 0 < y.factorization a := by
      have : a ∈ y.factorization.support := by rwa [Nat.support_factorization]
      exact Nat.pos_of_ne_zero (Finsupp.mem_support_iff.mp this)
    have hb_pos : 0 < y.factorization b := by
      have : b ∈ y.factorization.support := by rwa [Nat.support_factorization]
      exact Nat.pos_of_ne_zero (Finsupp.mem_support_iff.mp this)
    have hsub : ({a, b} : Finset ℕ) ⊆ y.primeFactors := by
      simp [Finset.insert_subset_iff, ha, hb]
    have h_ab_prod : (y.factorization a + 1) * (y.factorization b + 1) ≤
        ∏ p ∈ y.primeFactors, (y.factorization p + 1) := by
      calc (y.factorization a + 1) * (y.factorization b + 1)
          = ∏ p ∈ ({a, b} : Finset ℕ), (y.factorization p + 1) := by
            rw [Finset.prod_pair hab]
        _ ≤ ∏ p ∈ y.primeFactors, (y.factorization p + 1) := by
            apply Finset.prod_le_prod_of_subset_of_one_le' hsub
            intros; omega
    nlinarith [hprod.symm ▸ h_ab_prod]
  obtain ⟨p, hp⟩ := Finset.card_eq_one.mp hcard_one
  exact ⟨p, Nat.prime_of_mem_primeFactors (hp ▸ Finset.mem_singleton_self p), hp⟩

end Problems.Minif2f.mathd_numbertheory_221
