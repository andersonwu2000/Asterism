import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- uicc_uncountable: non-degenerate real interval has continuum cardinality, not countable
-- Uses Cardinal.mk_Icc_real to lift Set.uIcc a b (= Set.Icc (a⊓b) (a⊔b)) to continuum,
-- then contradicts Set.Countable via Cardinal.mk_le_aleph0_iff + aleph0_lt_continuum.
theorem uicc_uncountable (a b : ℝ) (hab : a ≠ b) : ¬ (Set.uIcc a b).Countable := by
  intro h
  have hlt : a ⊓ b < a ⊔ b := inf_lt_sup.mpr hab
  have hmk : Cardinal.mk ↑(Set.Icc (a ⊓ b) (a ⊔ b)) = Cardinal.continuum :=
    Cardinal.mk_Icc_real hlt
  have hcount : Cardinal.mk ↑(Set.Icc (a ⊓ b) (a ⊔ b)) ≤ Cardinal.aleph0 :=
    Cardinal.mk_le_aleph0_iff.mpr h
  exact absurd (hmk ▸ hcount) (not_le.mpr Cardinal.aleph0_lt_continuum)

end Problems.Geometry.banach_tarski
