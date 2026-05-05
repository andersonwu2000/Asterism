import Mathlib

namespace Problems.proj_nonexpansive

theorem s168_sub_1 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hConv : Convex ℝ K)
    (Px x z : X)
    (hPx_mem : Px ∈ K)
    (hPx_min : ∀ w ∈ K, ‖x - Px‖ ≤ ‖x - w‖)
    (hz : z ∈ K)
    (t : ℝ) (ht0 : 0 < t) (ht1 : t < 1) :
    2 * @inner ℝ X _ (x - Px) (z - Px) ≤ t * ‖z - Px‖ ^ 2 := by
  have hconv_mem : (1 - t) • Px + t • z ∈ K :=
    hConv hPx_mem hz (by linarith) (le_of_lt ht0) (by ring)
  have hle : ‖x - Px‖ ≤ ‖x - ((1 - t) • Px + t • z)‖ := hPx_min _ hconv_mem
  have hrw : x - ((1 - t) • Px + t • z) = (x - Px) - t • (z - Px) := by
    simp only [smul_sub, sub_smul, one_smul]; abel
  rw [hrw] at hle
  have hle_sq : ‖x - Px‖ ^ 2 ≤ ‖(x - Px) - t • (z - Px)‖ ^ 2 := by
    nlinarith [norm_nonneg (x - Px), norm_nonneg ((x - Px) - t • (z - Px))]
  have hexpand : ‖(x - Px) - t • (z - Px)‖ ^ 2 =
      ‖x - Px‖ ^ 2 - 2 * (t * @inner ℝ X _ (x - Px) (z - Px)) +
      t ^ 2 * ‖z - Px‖ ^ 2 := by
    rw [norm_sub_sq_real (x - Px) (t • (z - Px)), inner_smul_right, norm_smul,
        Real.norm_of_nonneg (le_of_lt ht0)]
    ring
  have hkey : 2 * t * @inner ℝ X _ (x - Px) (z - Px) ≤ t ^ 2 * ‖z - Px‖ ^ 2 := by
    nlinarith [hle_sq.trans_eq hexpand]
  nlinarith [hkey]

end Problems.proj_nonexpansive
