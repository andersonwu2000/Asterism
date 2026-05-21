import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- partition_endpoints_in_unit_interval: monotone partition stays in [0,1] on each sub-interval
theorem partition_endpoints_in_unit_interval
    {n : ℕ} {t : ℕ → ℝ}
    (ht0 : t 0 = 0) (htn : t n = 1)
    (ht_mono : ∀ i, i < n → t i ≤ t (i + 1))
    (i : ℕ) (hi : i < n) :
    0 ≤ t i ∧ t (i + 1) ≤ 1 := by
  have hmono : ∀ k j, j + k ≤ n → t j ≤ t (j + k) := by
    intro k
    induction k with
    | zero => intro j _; simp
    | succ m ih =>
      intro j hjm
      have hle : j + m ≤ n := Nat.le_of_succ_le hjm
      have hlt : j + m < n := Nat.lt_of_succ_le hjm
      calc t j ≤ t (j + m) := ih j hle
        _ ≤ t (j + m + 1) := ht_mono (j + m) hlt
        _ = t (j + (m + 1)) := by congr 1
  constructor
  · have h := hmono i 0 (by omega)
    simp at h
    linarith [h, ht0.symm ▸ (le_refl (t 0))]
  · have h := hmono (n - (i + 1)) (i + 1) (by omega)
    have heq : i + 1 + (n - (i + 1)) = n := by omega
    rw [heq] at h
    linarith [h, htn ▸ (le_refl (t n))]

end Problems.residue_thm
