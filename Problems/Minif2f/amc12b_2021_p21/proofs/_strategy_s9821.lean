import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- Direct chord inequality from concavity: parameterize z = (1-t)·a + t·b with t = (z-a)/(b-a),
-- apply ConcaveOn.2 at a,b with weights (1-t), t; f(a)=0 collapses the LHS to t·f(b) ≤ f(z),
-- then clear denominator (b-a > 0).
theorem s9821 :
    ∀ {f : ℝ → ℝ} {a b : ℝ}, a < b →
        ConcaveOn ℝ (Set.Icc a b) f → f a = 0 →
        ∀ z : ℝ, a ≤ z → z ≤ b → (z - a) * f b ≤ (b - a) * f z  := by
  intro f a b hab hconcave hfa z hza hzb
  have hba_pos : 0 < b - a := by linarith
  set t := (z - a) / (b - a) with ht_def
  have ht_nn : 0 ≤ t := div_nonneg (by linarith) (by linarith)
  have ht_le : t ≤ 1 := (div_le_one hba_pos).mpr (by linarith)
  have h1t_nn : 0 ≤ 1 - t := by linarith
  have ha_mem : a ∈ Set.Icc a b := ⟨le_refl a, le_of_lt hab⟩
  have hb_mem : b ∈ Set.Icc a b := ⟨le_of_lt hab, le_refl b⟩
  have hsum : (1 - t) + t = 1 := by ring
  have hcv := hconcave.2 ha_mem hb_mem h1t_nn ht_nn hsum
  have hz_eq : (1 - t) * a + t * b = z := by
    rw [ht_def]
    field_simp
    ring
  rw [hfa] at hcv
  simp only [smul_eq_mul, mul_zero, zero_add] at hcv
  rw [hz_eq] at hcv
  have key : (z - a) / (b - a) * f b ≤ f z := hcv
  rw [div_mul_eq_mul_div, div_le_iff₀ hba_pos] at key
  linarith

end Problems.Minif2f.amc12b_2021_p21
