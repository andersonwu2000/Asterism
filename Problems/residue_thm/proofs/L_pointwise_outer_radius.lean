import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- pointwise_outer_radius: each pole a ∈ T has a punctured ball where f is analytic,
-- found by shrinking a ball around a in U to avoid the finitely many other poles in T.
theorem pointwise_outer_radius
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ}
    (hU : IsOpen U) (hTU : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T)) :
    ∀ a ∈ T, ∃ r : ℝ, 0 < r ∧ AnalyticOn ℂ f (Metric.ball a r \ {a}) := by
  intro a haT
  have hTa_closed : IsClosed (↑(T.erase a) : Set ℂ) :=
    (T.erase a).finite_toSet.isClosed
  have hUa_open : IsOpen (U \ ↑(T.erase a)) := hU.sdiff hTa_closed
  have ha_mem : a ∈ U \ ↑(T.erase a) :=
    ⟨hTU a haT, by simp⟩
  obtain ⟨r, hr, hball⟩ := Metric.isOpen_iff.mp hUa_open a ha_mem
  exact ⟨r, hr, hf.mono (fun z hz =>
    ⟨(hball hz.1).1, fun hzT =>
      (hball hz.1).2 (Finset.mem_erase.mpr ⟨fun h => hz.2 (Set.mem_singleton_iff.mpr h), hzT⟩)⟩)⟩

end Problems.residue_thm

