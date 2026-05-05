import Mathlib
import Problems.proj_nonexpansive.proofs.L_s168_sub_1
import Problems.proj_nonexpansive.proofs.L_s168_sub_2

namespace Problems.proj_nonexpansive

theorem s168 {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X} (hK : IsClosed K) (hConv : Convex ℝ K) (hNe : K.Nonempty)
    (Px x z : X)
    (hPx_mem : Px ∈ K)
    (hPx_min : ∀ w ∈ K, ‖x - Px‖ ≤ ‖x - w‖)
    (hz : z ∈ K) :
    @inner ℝ X _ (Px - x) (z - Px) ≥ 0  := by
  have hpt : ∀ t : ℝ, 0 < t → t < 1 →
      2 * @inner ℝ X _ (x - Px) (z - Px) ≤ t * ‖z - Px‖ ^ 2 :=
    fun t ht0 ht1 => s168_sub_1 hConv Px x z hPx_mem hPx_min hz t ht0 ht1
  have hle : @inner ℝ X _ (x - Px) (z - Px) ≤ 0 :=
    s168_sub_2 _ _ hpt
  have heq : @inner ℝ X _ (Px - x) (z - Px) = -@inner ℝ X _ (x - Px) (z - Px) := by
    rw [show (Px : X) - x = -(x - Px) from by abel, inner_neg_left]
  linarith

end Problems.proj_nonexpansive
