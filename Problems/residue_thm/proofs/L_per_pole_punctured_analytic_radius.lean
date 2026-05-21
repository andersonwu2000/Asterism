import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- per_pole_punctured_analytic_radius: shrink to a ball avoiding all other poles via
-- openness of U \ (T \ {a}), then restrict hf via AnalyticOn.mono
-- entry_kind: Builder
theorem per_pole_punctured_analytic_radius
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (a : ℂ) (ha : a ∈ T) :
    ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball a R \ {a}) := by
  have ha_mem_U : a ∈ U := hT a ha
  have hopen : IsOpen (U \ (↑T \ {a})) := by
    apply IsOpen.sdiff hU
    exact (T.finite_toSet.subset Set.diff_subset).isClosed
  have ha_mem : a ∈ U \ (↑T \ {a}) := ⟨ha_mem_U, by simp⟩
  rw [Metric.isOpen_iff] at hopen
  obtain ⟨R, hR_pos, hR_ball⟩ := hopen a ha_mem
  refine ⟨R, hR_pos, hf.mono (fun x ⟨hx_ball, hx_ne⟩ => ?_)⟩
  constructor
  · exact (hR_ball hx_ball).1
  · intro hxT
    have : x ∈ (↑T : Set ℂ) \ {a} := ⟨hxT, fun h => hx_ne (h ▸ rfl)⟩
    exact absurd this (hR_ball hx_ball).2

end Problems.residue_thm
