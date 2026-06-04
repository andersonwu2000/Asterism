import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- sum_icc_eq_sum_succ: arithmetic identity ∑ k ∈ Icc 1 m, k = ∑ i : Fin m, (i.val+1) in ℝ
-- via Finset.sum_nbij with bijection (i : Fin m) ↦ i.val+1 mapping univ onto Icc 1 m
theorem sum_icc_eq_sum_succ :
    ∀ (n : ℕ) (a : ℕ → ℕ), Function.Injective a → a 0 = 0 →
    ∀ m, m ≤ n →
    ∀ (s : Finset ℕ) (hcard : s.card = m), (∀ x ∈ s, 1 ≤ x) →
      (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) = ∑ i : Fin m, ((i.val + 1 : ℕ) : ℝ) := by
  intro n a _ _ m _ s _ _
  symm
  apply Finset.sum_nbij (fun i => i.val + 1)
  · intro i _; simp [Finset.mem_Icc]
  · intro i₁ _ i₂ _ h
    exact Fin.ext (by simp at h; omega)
  · intro k hk
    simp at hk
    exact ⟨⟨k - 1, by omega⟩, Finset.mem_univ _, by simp; omega⟩
  · intro i _; push_cast; ring

end Problems.Minif2f.imo_1978_p5
