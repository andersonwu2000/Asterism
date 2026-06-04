import Mathlib
import Problems.Minif2f.imo_1967_p3.Defs
import Problems.Minif2f.imo_1967_p3.proofs.L_case_k_le_m
import Problems.Minif2f.imo_1967_p3.proofs.L_case_m_lt_k

namespace Problems.Minif2f.imo_1967_p3

-- Split on `k ≤ m` vs `m < k` to separate the two qualitatively different regimes.
-- `case_k_le_m`: real IMO-1967-P3 combinatorial argument (m+i > k for all i ≥ 1, no
-- ℕ-truncation, divisibility follows from the prime structure of k+m+1).
-- `case_m_lt_k`: trivial — at i=1, m+1 ≤ k so c(m+1) ≤ c(k), hence c(m+1) - c(k) = 0
-- in ℕ, making the right-hand product zero, which any nat divides.
-- Combinator: `by_cases hkm : k ≤ m` then `exact` each sub-lemma on its branch.
theorem s9380 : ∀ (k m n : ℕ) (c : ℕ → ℕ) (h₀ : 0 < k ∧ 0 < m ∧ 0 < n) (h₁ : ∀ s, c s = s * (s + 1)) (h₂ : Nat.Prime (k + m + 1)) (h₃ : n + 1 < k + m + 1), (∏ i ∈ Finset.Icc 1 n, c i) ∣ ∏ i ∈ Finset.Icc 1 n, c (m + i) - c k  := by
  intro k m n c h₀ h₁ h₂ h₃
  by_cases hkm : k ≤ m
  · exact case_k_le_m k m n c h₀ h₁ h₂ h₃ hkm
  · exact case_m_lt_k k m n c h₀ h₁ h₂ h₃ (Nat.lt_of_not_le hkm)

end Problems.Minif2f.imo_1967_p3
