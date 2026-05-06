-- convex_combo_in_set: proved by hint: aesop
import Mathlib
import Problems.proj_nonexpansive.Defs

namespace Problems.proj_nonexpansive

-- entry_kind: Builder
theorem convex_combo_in_set {X : Type*} [AddCommGroup X] [Module ℝ X]
    {K : Set X} (hK : Convex ℝ K) {a b : X} (ha : a ∈ K) (hb : b ∈ K)
    (t : ℝ) (ht0 : 0 ≤ t) (ht1 : t ≤ 1) : (1 - t) • a + t • b ∈ K := by aesop

end Problems.proj_nonexpansive
