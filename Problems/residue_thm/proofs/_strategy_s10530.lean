import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_c2_loop_piecewise_interp_balls_collapse_safe

namespace Problems.residue_thm

-- (A) Abstract a piecewise C² interpolation through an arbitrary point sequence
--     `p : ℕ → ℂ` confined to per-piece balls, with a collapse-safety hypothesis
--     resolving the prior parent_needs_fix: when `t i = t (i+1)`, `p i = p (i+1)`.
-- Instantiate `p := γ ∘ t`: collapse-safety is automatic since `p` is a function
-- of `t`; loop closure `p n = p 0` follows from `γ 0 = γ 1`, `ht0`, `htn`; per-step
-- ball-membership comes from `hgammacov` at the interval endpoints.
theorem s10530
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1)
    (n : ℕ) (t : ℕ → ℝ) (centers : ℕ → ℂ) (radii : ℕ → ℝ)
    (ht0 : t 0 = 0) (htn : t n = 1)
    (htmono : ∀ i, i < n → t i ≤ t (i+1))
    (hrpos : ∀ i, i < n → 0 < radii i)
    (hballsubU : ∀ i, i < n → Metric.ball (centers i) (radii i) ⊆ U)
    (hgammacov : ∀ i, i < n →
      Set.MapsTo γ (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) :
    ∃ (η : ℝ → ℂ),
      ContDiffOn ℝ 2 η (Set.Icc (0:ℝ) 1) ∧
      Set.MapsTo η (Set.Icc (0:ℝ) 1) U ∧
      η 0 = η 1 ∧
      η 0 = γ 0 ∧
      (∀ i, i < n →
        Set.MapsTo η (Set.Icc (t i) (t (i+1))) (Metric.ball (centers i) (radii i))) ∧
      (∀ i, i ≤ n → η (t i) = γ (t i))  := by
  have h_step :=
    c2_loop_piecewise_interp_balls_collapse_safe (n := n) (t := t)
      (p := fun i => γ (t i)) (centers := centers) (radii := radii)
      hU ht0 htn htmono hrpos hballsubU
      (fun i hi => hgammacov i hi (Set.left_mem_Icc.mpr (htmono i hi)))
      (fun i hi => hgammacov i hi (Set.right_mem_Icc.mpr (htmono i hi)))
      (by simp [ht0, htn, hclosed.symm])
      (fun i _ heq => by simp [heq])
  obtain ⟨η, hC2, hMaps, hLoop, hStart, hCov, hMatch⟩ := h_step
  refine ⟨η, hC2, hMaps, hLoop, ?_, hCov, hMatch⟩
  rw [hStart]
  change γ (t 0) = γ 0
  rw [ht0]

end Problems.residue_thm

