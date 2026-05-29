import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_preconnected_real_two_points_uncountable

namespace Problems.Geometry.banach_tarski

-- Reduce uncountability of a preconnected two-point set to the real-line case
-- via the continuous map x ↦ dist x p: its image is preconnected, contains 0 and
-- dist q p (distinct, since p ≠ q), so the abstract ℝ lemma makes the image
-- uncountable; were S countable the image would be countable — contradiction.
theorem s11525 {X : Type*} [MetricSpace X] {S : Set X}
    {p q : X} (h : IsPreconnected S) (hp : p ∈ S) (hq : q ∈ S) (hpq : p ≠ q) :
    ¬ S.Countable  := by
  intro hc
  have hcont : Continuous (fun x => dist x p) := by fun_prop
  have hT : IsPreconnected ((fun x => dist x p) '' S) := h.image _ hcont.continuousOn
  have hcountT : ((fun x => dist x p) '' S).Countable := hc.image _
  have ha : (0:ℝ) ∈ (fun x => dist x p) '' S := ⟨p, hp, by simp⟩
  have hb : dist q p ∈ (fun x => dist x p) '' S := ⟨q, hq, rfl⟩
  have hab : (0:ℝ) ≠ dist q p := by
    simp only [ne_eq, eq_comm (a := (0:ℝ)), dist_eq_zero]
    exact fun h => hpq h.symm
  exact preconnected_real_two_points_uncountable _ hT 0 (dist q p) ha hb hab hcountT

end Problems.Geometry.banach_tarski
