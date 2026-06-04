import Mathlib
import Problems.Minif2f.imo_1987_p4.Defs
import Problems.Minif2f.imo_1987_p4.proofs.L_lt_card_eq_gt_card
import Problems.Minif2f.imo_1987_p4.proofs.L_nonfixed_split_lt_gt

namespace Problems.Minif2f.imo_1987_p4

-- Decompose `2 ∣ #{a < 1987 | g a ≠ a}` via trichotomy + the involution-induced bijection.
-- (1) `nonfixed_split_lt_gt`: split the non-fixed-point count into `a < g a` plus `g a < a`.
-- (2) `lt_card_eq_gt_card`: the involution `g` bijects `{a < g a}` with `{g a < a}`.
-- Adding two equal cardinalities yields `2 * _`, hence `2 ∣ _`.
theorem s9784 :
    ∀ (g : ℕ → ℕ), (∀ a, a < 1987 → g a < 1987) →
      (∀ a, a < 1987 → g (g a) = a) →
      2 ∣ (Finset.filter (fun a => g a ≠ a) (Finset.range 1987)).card := by
  intro g hg hgg
  have h_split := nonfixed_split_lt_gt g hg hgg
  have h_equal := lt_card_eq_gt_card g hg hgg
  rw [h_split, h_equal, ← two_mul]
  exact ⟨_, rfl⟩

end Problems.Minif2f.imo_1987_p4
