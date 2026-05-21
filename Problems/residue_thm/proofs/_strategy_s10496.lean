import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_partition_subdivides_path_in_ball_2
import Problems.residue_thm.proofs.L_uniform_ball_thickening_of_path_2

namespace Problems.residue_thm

-- Compose two siblings: (A) `uniform_ball_thickening_of_path_2` yields a single
-- positive radius δ with `ball (γ t) δ ⊆ U` uniformly in t (compactness +
-- Lebesgue-number on the open cover of γ([0,1])); (B) `partition_subdivides_path_in_ball_2`
-- partitions [0,1] so each subarc lands in `ball (γ (tᵢ)) δ`. Centers
-- `c i := γ (t i)`, radii `r i := δ` package the cover required by the parent.
theorem s10496
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    ∃ (n : ℕ) (t : ℕ → ℝ) (c : ℕ → ℂ) (r : ℕ → ℝ),
      t 0 = 0 ∧ t n = 1 ∧
      (∀ i, i < n → t i ≤ t (i + 1)) ∧
      (∀ i, i < n → 0 < r i) ∧
      (∀ i, i < n → Metric.ball (c i) (r i) ⊆ U) ∧
      (∀ i, i < n → Set.MapsTo γ (Set.Icc (t i) (t (i + 1)))
        (Metric.ball (c i) (r i)))  := by
  obtain ⟨δ, hδpos, hδball⟩ := uniform_ball_thickening_of_path_2 hU hγ hmaps
  obtain ⟨n, t, ht0, htn, htmono, htmem, hsub⟩ :=
    partition_subdivides_path_in_ball_2 hU hγ hmaps δ hδpos
  refine ⟨n, t, (fun i => γ (t i)), (fun _ => δ), ht0, htn, htmono, ?_, ?_, ?_⟩
  · intro i _
    exact hδpos
  · intro i hi
    exact hδball (t i) (htmem i hi.le)
  · intro i hi
    exact hsub i hi

end Problems.residue_thm
