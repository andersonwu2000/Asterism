import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem tendsto_segment_integral_from_uniform_smallness
    (Q : ℂ → ℂ) (z : ℂ)
    (h_unif : ∀ ε : ℝ, 0 < ε → ∀ᶠ h : ℂ in nhds 0,
      ∀ t : ℝ, t ∈ Set.Icc (0:ℝ) 1 → ‖Q (z + (t : ℂ) * h) - Q z‖ ≤ ε) :
    Filter.Tendsto (fun h : ℂ => ∫ t in (0:ℝ)..1, Q (z + (t : ℂ) * h))
      (nhds 0) (nhds (Q z)) := by sorry

end Problems.residue_thm
