import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_root_sqrt2_or_gt_three
import Problems.Minif2f.amc12b_2021_p21.proofs.L_unique_root_gt_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Decompose `S.card ≤ 2` via two structural facts about the equation
-- `x ^ (2 ^ √2) = √2 ^ (2 ^ x)` on (0, ∞):
--   (a) every positive solution is either √2 or strictly greater than 3;
--   (b) at most one positive solution lies above 3.
-- Then S ⊆ insert √2 (S.filter (3 < ·)), and the filtered part has card ≤ 1.
theorem s9668 : ∀ (S : Finset ℝ) (_ : ∀ x : ℝ, x ∈ S ↔ 0 < x ∧ x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x), S.card ≤ 2  := by
  intro S hS
  have h_split := root_sqrt2_or_gt_three
  have h_unique := unique_root_gt_three
  set T : Finset ℝ := S.filter (3 < ·) with hT_def
  have hT_card : T.card ≤ 1 := by
    rcases T.card.eq_zero_or_pos with h0 | hpos
    · omega
    · obtain ⟨a, ha⟩ := Finset.card_pos.mp hpos
      have hy_mem_a := Finset.mem_filter.mp ha
      have ha_S := (hS a).mp hy_mem_a.1
      have hT_sub : T ⊆ ({a} : Finset ℝ) := by
        intro y hy
        have hy_mem := Finset.mem_filter.mp hy
        have hy_S := (hS y).mp hy_mem.1
        rw [Finset.mem_singleton]
        exact h_unique y a hy_S.1 ha_S.1 hy_mem.2 hy_mem_a.2 hy_S.2 ha_S.2
      have := Finset.card_le_card hT_sub
      simpa using this
  have h_sub : S ⊆ insert (Real.sqrt 2) T := by
    intro x hx
    have hx_S := (hS x).mp hx
    rcases h_split x hx_S.1 hx_S.2 with h1 | h2
    · exact h1 ▸ Finset.mem_insert_self _ _
    · exact Finset.mem_insert_of_mem (Finset.mem_filter.mpr ⟨hx, h2⟩)
  calc S.card ≤ (insert (Real.sqrt 2) T).card := Finset.card_le_card h_sub
    _ ≤ T.card + 1 := Finset.card_insert_le _ _
    _ ≤ 1 + 1 := by omega
    _ = 2 := rfl

end Problems.Minif2f.amc12b_2021_p21
