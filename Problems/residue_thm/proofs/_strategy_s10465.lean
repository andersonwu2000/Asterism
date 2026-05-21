import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct (leaf) proof. Build `g` pointwise: pick a local extension `g_pole a`
-- at each pole via `choose` on `h_loc`, then set `g z := g_pole z _ z` for
-- `z ∈ T` and `g z := f z - ∑ P a z` elsewhere. Analyticity on `U`: on the
-- open complement `U \ T` the function agrees with `h_F_anal` on a
-- neighborhood; at a pole `a`, `hper`'s separation gives `g = g_pole a _`
-- throughout `Metric.ball a (R a)`, so analyticity transfers via
-- `AnalyticAt.congr`. The equality on `U \ T` is by `dif_neg`.
theorem s10465
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ)
    (hper : ∀ a ∈ T,
      0 < R a ∧
      Metric.ball a (R a) ⊆ U ∧
      (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
      AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
      Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z))
    (h_F_anal : AnalyticOn ℂ (fun z => f z - ∑ a ∈ T, P a z) (U \ ↑T))
    (h_loc : ∀ a ∈ T, ∃ (g_a : ℂ → ℂ),
      AnalyticOn ℂ g_a (Metric.ball a (R a)) ∧
      ∀ z ∈ Metric.ball a (R a) \ {a}, g_a z = f z - ∑ b ∈ T, P b z) :
    ∃ (g : ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ z ∈ U \ ↑T, g z = f z - ∑ a ∈ T, P a z)  := by
  classical
  choose g_pole hg_pole_anal hg_pole_eq using h_loc
  refine ⟨fun z => if hz : z ∈ T then g_pole z hz z else f z - ∑ a ∈ T, P a z,
    ?_, ?_⟩
  · rw [hU.analyticOn_iff_analyticOnNhd]
    intro x hx
    by_cases hxT : x ∈ T
    · have hRx : 0 < R x := (hper x hxT).1
      have hother : ∀ b ∈ T, b ≠ x → b ∉ Metric.ball x (R x) :=
        (hper x hxT).2.2.1
      have hball_nhds : Metric.ball x (R x) ∈ nhds x :=
        Metric.ball_mem_nhds _ hRx
      have hG_eq : (fun z => if hz : z ∈ T then g_pole z hz z
            else f z - ∑ a ∈ T, P a z) =ᶠ[nhds x] g_pole x hxT := by
        filter_upwards [hball_nhds] with z hz
        by_cases hzT : z ∈ T
        · have hzeqx : z = x := by
            by_contra hzne
            exact hother z hzT hzne hz
          subst hzeqx
          simp [hzT]
        · have hz_punctured : z ∈ Metric.ball x (R x) \ {x} :=
            ⟨hz, fun hzx => hzT (hzx ▸ hxT)⟩
          have heq := hg_pole_eq x hxT z hz_punctured
          simp only [dif_neg hzT]
          exact heq.symm
      have hap : AnalyticAt ℂ (g_pole x hxT) x :=
        (hg_pole_anal x hxT).analyticAt hball_nhds
      exact hap.congr hG_eq.symm

    · have hxUT : x ∈ U \ ↑T := ⟨hx, hxT⟩
      have hT_closed : IsClosed (↑T : Set ℂ) := T.finite_toSet.isClosed
      have hUT_open : IsOpen (U \ ↑T) := hU.sdiff hT_closed
      have hUT_nhds : U \ ↑T ∈ nhds x := hUT_open.mem_nhds hxUT
      have hG_eq : (fun z => if hz : z ∈ T then g_pole z hz z
            else f z - ∑ a ∈ T, P a z) =ᶠ[nhds x]
          (fun z => f z - ∑ a ∈ T, P a z) := by
        filter_upwards [hUT_nhds] with z hz
        have hzT : z ∉ T := fun h => hz.2 (Finset.mem_coe.mpr h)
        simp only [dif_neg hzT]
      have hap : AnalyticAt ℂ (fun z => f z - ∑ a ∈ T, P a z) x :=
        h_F_anal.analyticAt hUT_nhds
      exact hap.congr hG_eq.symm
  · intro z hz
    have hzT : z ∉ T := fun h => hz.2 (Finset.mem_coe.mpr h)
    simp only [dif_neg hzT]

end Problems.residue_thm