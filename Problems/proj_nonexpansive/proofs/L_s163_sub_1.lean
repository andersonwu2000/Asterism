import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

theorem s163_sub_1 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hK : IsClosed K) (hConv : Convex ℝ K) (hNe : K.Nonempty)
    {P : X → X} (hP : IsMetricProjector K P)
    (x z : X) (hz : z ∈ K)
    (t : ℝ) (ht : 0 < t) (ht1 : t ≤ 1) :
    2 * t * @inner ℝ X _ (x - P x) (z - P x) ≤ t ^ 2 * ‖z - P x‖ ^ 2 := by
  obtain ⟨hPx_mem, hPx_min⟩ := hP x
  have hconv_mem : (1 - t) • P x + t • z ∈ K :=
    hConv hPx_mem hz (by linarith) (le_of_lt ht) (by ring)
  have hle : ‖x - P x‖ ≤ ‖x - ((1 - t) • P x + t • z)‖ := hPx_min _ hconv_mem
  have hrw : x - ((1 - t) • P x + t • z) = (x - P x) - t • (z - P x) := by
    simp only [smul_sub, sub_smul, one_smul]; abel
  rw [hrw] at hle
  have hle_sq : ‖x - P x‖ ^ 2 ≤ ‖(x - P x) - t • (z - P x)‖ ^ 2 := by
    nlinarith [norm_nonneg (x - P x), norm_nonneg ((x - P x) - t • (z - P x))]
  have hexpand : ‖(x - P x) - t • (z - P x)‖ ^ 2 =
      ‖x - P x‖ ^ 2 - 2 * (t * @inner ℝ X _ (x - P x) (z - P x)) +
      t ^ 2 * ‖z - P x‖ ^ 2 := by
    rw [norm_sub_sq_real (x - P x) (t • (z - P x)), inner_smul_right, norm_smul,
        Real.norm_of_nonneg (le_of_lt ht)]
    ring
  nlinarith [hle_sq.trans_eq hexpand]

end Problems.proj_nonexpansive
