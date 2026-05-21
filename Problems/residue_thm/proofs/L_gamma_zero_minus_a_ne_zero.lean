import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- gamma_zero_minus_a_ne_zero: Set.MapsTo gives γ 0 ∈ U \ ↑T, so γ 0 ∉ T; since a ∈ T, γ 0 ≠ a, hence γ 0 - a ≠ 0
theorem gamma_zero_minus_a_ne_zero
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    γ 0 - a ≠ 0 := by
  intro h
  have h0 : (0 : ℝ) ∈ Set.Icc (0 : ℝ) 1 := by norm_num
  have hγ0 : γ 0 ∈ U \ ↑T := hmap h0
  have hγ0T : γ 0 ∉ ↑T := hγ0.2
  have haT : a ∈ ↑T := Finset.mem_coe.mpr ha
  have hne : γ 0 ≠ a := fun heq => hγ0T (heq ▸ haT)
  exact hne (sub_eq_zero.mp h)

end Problems.residue_thm
