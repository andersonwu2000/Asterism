import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem cocompact_decay_of_diff_extension
    {a : ℂ} {Q1 Q2 : ℂ → ℂ}
    (hQ1_tendsto : Filter.Tendsto Q1 (Filter.cocompact ℂ) (nhds 0))
    (hQ2_tendsto : Filter.Tendsto Q2 (Filter.cocompact ℂ) (nhds 0))
    (h_ext : ℂ → ℂ)
    (h_agree : ∀ w, w ≠ a → h_ext w = Q1 w - Q2 w) :
    Filter.Tendsto h_ext (Filter.cocompact ℂ) (nhds 0) := by sorry

end Problems.residue_thm
