import Mathlib
import Problems.proj_nonexpansive.Defs
import Problems.proj_nonexpansive.proofs.L_convex_combo_in_set
import Problems.proj_nonexpansive.proofs.L_inner_le_zero_of_norm_le

namespace Problems.proj_nonexpansive

theorem s2 : ∀ {X : Type*} [NormedAddCommGroup X] [InnerProductSpace ℝ X]
    {K : Set X}, IsClosed K → Convex ℝ K → K.Nonempty →
    ∀ {P : X → X}, IsMetricProjector K P →
    ∀ z : X, ∀ w ∈ K, @inner ℝ _ _ (P z - z) (w - P z) ≥ 0  := by
  intro X _ _ K _hclosed hconvex _hne P hP z w hw
  have hPzK : P z ∈ K := (hP z).1
  have h_norm : ∀ t : ℝ, 0 < t → t ≤ 1 → ‖z - P z‖ ≤ ‖(z - P z) - t • (w - P z)‖ := by
    intro t ht0 ht1
    have h1 : (1 - t) • P z + t • w ∈ K :=
      convex_combo_in_set hconvex hPzK hw t (le_of_lt ht0) ht1
    have h2 := (hP z).2 _ h1
    have heq : z - ((1 - t) • P z + t • w) = (z - P z) - t • (w - P z) := by
      simp only [smul_sub, sub_smul, one_smul]; abel
    rw [← heq]; exact h2
  have hle : @inner ℝ _ _ (z - P z) (w - P z) ≤ 0 :=
    inner_le_zero_of_norm_le _ _ h_norm
  have hsign : @inner ℝ _ _ (P z - z) (w - P z) = -@inner ℝ _ _ (z - P z) (w - P z) := by
    have heq : P z - z = -(z - P z) := by abel
    rw [heq, inner_neg_left]
  linarith

end Problems.proj_nonexpansive
