import Mathlib
namespace Problems.Minif2f.aime_1983_p9

-- am_gm_core: (3t-2)² ≥ 0 gives 9t²+4 ≥ 12t; divide by t > 0 via le_div_iff₀
theorem am_gm_core : ∀ (t : ℝ), 0 < t → 12 ≤ (9 * t ^ 2 + 4) / t := by
  intro t ht
  have ht' : t ≠ 0 := ne_of_gt ht
  have h1 : 12 * t ≤ 9 * t ^ 2 + 4 := by nlinarith [sq_nonneg (3 * t - 2)]
  have h2 : 12 ≤ (9 * t ^ 2 + 4) / t := by
    rwa [le_div_iff₀ ht]
  exact h2

end Problems.Minif2f.aime_1983_p9
