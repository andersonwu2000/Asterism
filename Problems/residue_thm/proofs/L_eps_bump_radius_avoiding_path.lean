import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- eps_bump_radius_avoiding_path: compactness gives infimum of dist(γ t, a) > ε;
-- take r = (ε + inf)/2 strictly between ε and the infimum.
theorem eps_bump_radius_avoiding_path
    {γ : ℝ → ℂ} {a : ℂ} {ε : ℝ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hε_pos : 0 < ε)
    (hε_sep : ∀ t ∈ Set.Icc (0 : ℝ) 1, ε < dist (γ t) a) :
    ∃ r : ℝ, ε < r ∧ ∀ t ∈ Set.Icc (0 : ℝ) 1, r < dist (γ t) a := by
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hcont : ContinuousOn (fun t => dist (γ t) a) (Set.Icc 0 1) := by fun_prop
  have hne : (Set.Icc (0 : ℝ) 1).Nonempty := ⟨0, by norm_num⟩
  obtain ⟨t₀, ht₀_mem, ht₀_min⟩ := isCompact_Icc.exists_isMinOn hne hcont
  refine ⟨(ε + dist (γ t₀) a) / 2, by linarith [hε_sep t₀ ht₀_mem], ?_⟩
  intro t ht
  have hle : dist (γ t₀) a ≤ dist (γ t) a := ht₀_min ht
  linarith [hε_sep t₀ ht₀_mem]

end Problems.residue_thm
