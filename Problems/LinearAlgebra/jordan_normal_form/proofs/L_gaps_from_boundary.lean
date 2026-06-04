import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- entry_kind: Builder
-- Witness: l t = B(t+1) - B(t) where B i = if i < p then b ⟨i,_⟩ else n.
-- Positivity: B strictly increases (StrictMono b / hlt).
-- Sum = n: Finset.sum_range_tsub telescopes B p - B 0 = n - 0.
-- Prefix = b t: same telescoping to B t - B 0 = b t.
-- Self-contained (no sibling imports) to avoid triggering rebuild of broken _strategy_s10936.
theorem gaps_from_boundary {n p : ℕ} (b : Fin p → ℕ)
    (hmono : StrictMono b) (hlt : ∀ t : Fin p, b t < n)
    (hzero : ∀ t : Fin p, (t : ℕ) = 0 → b t = 0)
    (hp : 0 < n → 0 < p) :
    ∃ l : Fin p → ℕ,
      (∀ t : Fin p, 0 < l t) ∧ (∑ t, l t = n) ∧
      (∀ t : Fin p, (∑ j : Fin ↑t, l (Fin.castLE t.isLt.le j)) = b t) := by
  -- Extended boundary on ℕ
  set B : ℕ → ℕ := fun i => if h : i < p then b ⟨i, h⟩ else n with hB_def
  have hBmono : Monotone B := by
    intro i j hij
    simp only [hB_def]
    by_cases hi : i < p
    · by_cases hj : j < p
      · rw [dif_pos hi, dif_pos hj]
        exact hmono.le_iff_le.2 (Fin.mk_le_mk.2 hij)
      · rw [dif_pos hi, dif_neg hj]; exact (hlt ⟨i, hi⟩).le
    · have hj : ¬ j < p := fun hc => hi (Nat.lt_of_le_of_lt hij hc)
      rw [dif_neg hi, dif_neg hj]
  have hB_val : ∀ t : Fin p, B t.val = b t := fun t => dif_pos t.isLt
  have hBp : B p = n := dif_neg (lt_irrefl p)
  have hB0 : B 0 = 0 := by
    simp only [hB_def]
    rcases Nat.eq_zero_or_pos p with rfl | hp0
    · -- p = 0 forces n = 0 via hp
      rw [dif_neg (Nat.lt_irrefl 0)]
      rcases Nat.eq_zero_or_pos n with rfl | hn
      · rfl
      · have := hp hn; omega
    · rw [dif_pos hp0]; exact hzero ⟨0, hp0⟩ rfl
  refine ⟨fun t => B (t.val + 1) - B t.val, ?_, ?_, ?_⟩
  · -- Positivity
    intro t
    apply Nat.sub_pos_of_lt
    simp only [hB_def, dif_pos t.isLt]
    by_cases h : t.val + 1 < p
    · rw [dif_pos h]; exact hmono (by simp [Fin.lt_def])
    · rw [dif_neg h]; exact hlt t
  · -- Total sum = n
    rw [Fin.sum_univ_eq_sum_range (fun i => B (i + 1) - B i) p,
        Finset.sum_range_tsub hBmono, hBp, hB0, Nat.sub_zero]
  · -- Prefix sums = b t
    intro t
    -- Fin.castLE preserves .val, so simp it away before telescoping
    simp only [Fin.val_castLE]
    rw [Fin.sum_univ_eq_sum_range (fun i => B (i + 1) - B i) t.val,
        Finset.sum_range_tsub hBmono, hB_val t, hB0, Nat.sub_zero]

end Problems.LinearAlgebra.jordan_normal_form
