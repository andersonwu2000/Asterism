import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- gamma_sub_a_ne_zero_on_icc: γ s - a ≠ 0 on [0,1] via MapsTo into U \ T and a ∈ T.
-- hmap sends every s ∈ Icc 0 1 into U \ T, so γ s ∉ T; since a ∈ T, γ s ≠ a,
-- and sub_ne_zero closes the goal.
theorem gamma_sub_a_ne_zero_on_icc
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ∀ s ∈ Set.Icc (0:ℝ) 1, γ s - a ≠ 0 := by
  intro s hs
  have hmem := hmap hs
  simp only [Set.mem_diff, Finset.mem_coe] at hmem
  have hne : γ s ≠ a := fun heq => hmem.2 (heq ▸ ha)
  exact sub_ne_zero.mpr hne

end Problems.residue_thm
