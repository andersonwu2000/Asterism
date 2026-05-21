import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_left_branch_velocity_continuous
import Problems.residue_thm.proofs.L_right_branch_velocity_continuous

namespace Problems.residue_thm

-- Glue the piecewise velocity via `ContinuousOn.if`:
-- (1) continuity of the left branch `s ↦ 2·derivWithin α' (Icc 0 1) (2s)` on `Icc 0 (1/2)`,
-- (2) continuity of the right branch `s ↦ 2·derivWithin β' (Icc 0 1) (2s-1)` on `Icc (1/2) 1`,
-- (3) junction agreement at s = 1/2 follows inline from `hα'_deriv` and `hβ'_deriv`
--     (both branches evaluate to 0 there).
theorem s10667
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn
      (fun s : ℝ => if s ≤ (1:ℝ)/2
        then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      (Set.Icc 0 1)  := by
  have h_left_raw := left_branch_velocity_continuous hα' hβ' hα'_deriv hβ'_deriv
  have h_right_raw := right_branch_velocity_continuous hα' hβ' hα'_deriv hβ'_deriv
  have h_left : ContinuousOn (fun s : ℝ => 2 * derivWithin α' (Set.Icc 0 1) (2*s))
      (Set.Icc 0 1 ∩ closure {a : ℝ | a ≤ (1:ℝ)/2}) := by
    have hcl : closure {a : ℝ | a ≤ (1:ℝ)/2} = Set.Iic ((1:ℝ)/2) := isClosed_Iic.closure_eq
    rw [hcl]
    apply h_left_raw.mono
    intro x hx
    refine ⟨hx.1.1, ?_⟩
    exact hx.2
  have h_right : ContinuousOn (fun s : ℝ => 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))
      (Set.Icc 0 1 ∩ closure {a : ℝ | ¬ a ≤ (1:ℝ)/2}) := by
    have hcl : closure {a : ℝ | ¬ a ≤ (1:ℝ)/2} = Set.Ici ((1:ℝ)/2) := by
      have heq : {a : ℝ | ¬ a ≤ (1:ℝ)/2} = Set.Ioi ((1:ℝ)/2) := by
        ext x; simp [not_le, Set.mem_Ioi]
      rw [heq, closure_Ioi]
    rw [hcl]
    apply h_right_raw.mono
    intro x hx
    refine ⟨hx.2, hx.1.2⟩
  have h_junction : ∀ a ∈ Set.Icc (0:ℝ) 1 ∩ frontier {a : ℝ | a ≤ (1:ℝ)/2},
      2 * derivWithin α' (Set.Icc 0 1) (2*a) = 2 * derivWithin β' (Set.Icc 0 1) (2*a - 1) := by
    intro a ha
    have hfr : frontier {b : ℝ | b ≤ (1:ℝ)/2} = {(1:ℝ)/2} := by
      change frontier (Set.Iic ((1:ℝ)/2)) = {(1:ℝ)/2}
      exact frontier_Iic
    rw [hfr] at ha
    obtain ⟨_, ha'⟩ := ha
    simp only [Set.mem_singleton_iff] at ha'
    subst ha'
    simp [hα'_deriv, hβ'_deriv]
  exact h_left.if h_junction h_right

end Problems.residue_thm
