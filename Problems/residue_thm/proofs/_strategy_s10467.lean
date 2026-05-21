import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_isolating_radius_in_open_finset
import Problems.residue_thm.proofs.L_principal_part_at_singularity_step_wrapper

namespace Problems.residue_thm

-- Per-pole Skolemisation: case-split on `a ∈ T`. For poles, get an isolating
-- ball via `isolating_radius_in_open_finset` (purely topological: U open + T
-- finite + a ∈ T), restrict `hf` to that punctured ball, then apply the
-- Cauchy-Laurent split via `principal_part_at_singularity_step_wrapper`
-- (a Builder wrapper around the proved toolkit
-- `principal_part_extraction_at_singularity`, isolated per LESSONS so the
-- framework's auto-import for `_strategy_*.lean` picks it up). For non-poles,
-- supply dummy witnesses; the hypothesis `a ∈ T` is vacuously false.
theorem s10467
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∀ a : ℂ, ∃ (r : ℝ) (P_a h_a : ℂ → ℂ),
      a ∈ T →
      (0 < r ∧
       Metric.ball a r ⊆ U ∧
       (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a r) ∧
       AnalyticOn ℂ P_a (Set.univ \ {a}) ∧
       Filter.Tendsto P_a (Filter.cocompact ℂ) (nhds 0) ∧
       AnalyticOn ℂ h_a (Metric.ball a r) ∧
       (∀ z ∈ Metric.ball a r \ {a}, f z = h_a z + P_a z))  := by
  intro a
  by_cases ha : a ∈ T
  · obtain ⟨r, hr_pos, hr_subU, hr_iso⟩ :=
      isolating_radius_in_open_finset hU hT hf a ha
    have hf' : AnalyticOn ℂ f (Metric.ball a r \ {a}) := by
      apply hf.mono
      rintro z ⟨hzball, hz_ne⟩
      refine ⟨hr_subU hzball, ?_⟩
      intro hzT
      have hzne_a : z ≠ a := fun h => hz_ne (Set.mem_singleton_iff.mpr h)
      exact hr_iso z hzT hzne_a hzball
    obtain ⟨P, g, hP_an, hP_t, hg_an, hsum⟩ :=
      principal_part_at_singularity_step_wrapper hr_pos hf'
    exact ⟨r, P, g, fun _ => ⟨hr_pos, hr_subU, hr_iso, hP_an, hP_t, hg_an, hsum⟩⟩
  · exact ⟨1, 0, 0, fun haT => absurd haT ha⟩

end Problems.residue_thm
