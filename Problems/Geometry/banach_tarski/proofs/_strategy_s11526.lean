import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_uicc_uncountable

namespace Problems.Geometry.banach_tarski

-- A preconnected T ⊆ ℝ with two distinct points a, b is uncountable.
-- Preconnected ⇒ OrdConnected, so the nondegenerate interval uIcc a b ⊆ T
-- (inlined via hT.ordConnected.uIcc_subset). That interval is uncountable
-- (uicc_uncountable, the only sub-goal). If T were countable so would its
-- subset uIcc a b — contradiction.
theorem s11526 (T : Set ℝ) (hT : IsPreconnected T)
    (a b : ℝ) (ha : a ∈ T) (hb : b ∈ T) (hab : a ≠ b) : ¬ T.Countable  := by
  intro hc
  have h_subset : Set.uIcc a b ⊆ T := hT.ordConnected.uIcc_subset ha hb
  have h_unc : ¬ (Set.uIcc a b).Countable := uicc_uncountable a b hab
  exact h_unc (hc.mono h_subset)

end Problems.Geometry.banach_tarski
