import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- compose_c1_on_unit_interval: ContDiffOn.comp closes via hγ, hφ.contDiffOn, hφrange

theorem compose_c1_on_unit_interval
    {γ : ℝ → ℂ} {φ : ℝ → ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hφ : ContDiff ℝ 1 φ)
    (hφrange : ∀ t ∈ Set.Icc (0 : ℝ) 1, φ t ∈ Set.Icc (0 : ℝ) 1) :
    ContDiffOn ℝ 1 (γ ∘ φ) (Set.Icc 0 1) := by
  exact hγ.comp hφ.contDiffOn hφrange

end Problems.residue_thm
