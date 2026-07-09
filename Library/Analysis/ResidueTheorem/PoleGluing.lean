import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Calculus.ContDiff.Defs
import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Topology.GDelta.MetrizableSpace

/-!
# Pole gluing for the residue theorem

This file constructs a global analytic extension by gluing together local analytic pieces
around a finite set of poles.

Given an open set `U ⊆ ℂ`, a finite set of poles `T ⊆ U`, a function `f` analytic on `U \ T`,
and for each pole `a ∈ T` a principal part `P a` (analytic on `ℂ \ {a}`) together with an
analytic local correction `h a` on a ball around `a`, the main result
`exists_analyticOn_eq_add_sum` produces a globally analytic function `g : ℂ → ℂ` on `U`
such that `f z = g z + ∑ a ∈ T, P a z` for all `z ∈ U \ ↑T`.

## Main statements

- `exists_analyticOn_of_local_extensions`: glues local analytic extensions around each pole
  into a single analytic function on all of `U`.
- `exists_analyticOn_eq_add_sum`: the main decomposition `f = g + ∑ P a` on `U \ T`,
  where `g` is the globally analytic remainder.
-/

namespace Library.Analysis.ResidueTheorem.PoleGluing

/-- Glue local analytic extensions around finitely many poles into a single function analytic
on all of `U`.

Given `h_F_anal : f - ∑ P a` analytic on `U \ T` and `h_loc` providing for each pole
`a ∈ T` an extension `g_a` analytic on `Metric.ball a (R a)` that agrees with
`f - ∑ P b` on the punctured ball, this produces a global `g : ℂ → ℂ` analytic on `U`
with `g z = f z - ∑ a ∈ T, P a z` for all `z ∈ U \ ↑T`.

The construction sets `g z := g_pole z _ z` for `z ∈ T` (using `Classical.choose` on `h_loc`)
and `g z := f z - ∑ P a z` elsewhere; analyticity at a pole `a` follows from
`AnalyticAt.congr` via the separation property in `hper`. -/
theorem exists_analyticOn_of_local_extensions
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
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
      (∀ z ∈ U \ ↑T, g z = f z - ∑ a ∈ T, P a z) := by
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

/-- The function `f - ∑ a ∈ T, P a` is analytic on `U \ ↑T`.

Each principal part `P a` is analytic on `ℂ \ {a}` by `hper`, and restricts to an
analytic function on `U \ ↑T` since no pole `a` lies in `U \ ↑T`. -/
theorem analyticOn_sub_sum_sdiff
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ)
    (hper : ∀ a ∈ T,
      0 < R a ∧
      Metric.ball a (R a) ⊆ U ∧
      (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
      AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
      Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    AnalyticOn ℂ (fun z => f z - ∑ a ∈ T, P a z) (U \ ↑T) := by
  apply hf.sub
  apply T.analyticOn_fun_sum
  intro a ha
  apply (hper a ha).2.2.2.1.mono
  intro z hz
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
  intro heq
  exact hz.2 (heq ▸ Finset.mem_coe.mpr ha)

/-- For each pole `a ∈ T`, the function `h a - ∑ b ∈ T.erase a, P b` is analytic on
`Metric.ball a (R a)`.

Here `h a` is analytic on the ball by `hper`, and each `P b` with `b ≠ a` is analytic
on the ball because separation (`hper`) ensures `b ∉ Metric.ball a (R a)`, so `P b` is
analytic there (being analytic on `ℂ \ {b}`). -/
theorem analyticOn_ball_sub_sum_erase
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ)
    (hper : ∀ a ∈ T,
      0 < R a ∧
      Metric.ball a (R a) ⊆ U ∧
      (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
      AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
      Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    ∀ a ∈ T,
      AnalyticOn ℂ (fun z => h a z - ∑ b ∈ T.erase a, P b z)
        (Metric.ball a (R a)) := by
  intro a haT
  obtain ⟨hRpos, hball, hsep, hPana, hPtend, hhana, hfz⟩ := hper a haT
  refine hhana.sub ?_
  simp_rw [← Finset.sum_apply]
  exact Finset.analyticOn_sum _ fun b hb => by
    have hbT : b ∈ T := Finset.erase_subset a T hb
    have hbna : b ≠ a := (Finset.mem_erase.mp hb).1
    obtain ⟨_, _, _, hPb, _, _, _⟩ := hper b hbT
    apply hPb.mono
    intro z hz
    exact ⟨Set.mem_univ z, fun hzb => hsep b hbT hbna (hzb ▸ hz)⟩

/-- On the punctured ball `Metric.ball a (R a) \ {a}`, the candidate
`h a z - ∑ b ∈ T.erase a, P b z`
equals `f z - ∑ b ∈ T, P b z`.

This follows from `f z = h a z + P a z` (given by `hper`) and splitting the sum
`∑ b ∈ T, P b z = P a z + ∑ b ∈ T.erase a, P b z`. -/
theorem sub_sum_erase_eq_sub_sum_punctured_ball
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (P : ℂ → ℂ → ℂ) (R : ℂ → ℝ) (h : ℂ → ℂ → ℂ)
    (hper : ∀ a ∈ T,
      0 < R a ∧
      Metric.ball a (R a) ⊆ U ∧
      (∀ b ∈ T, b ≠ a → b ∉ Metric.ball a (R a)) ∧
      AnalyticOn ℂ (P a) (Set.univ \ {a}) ∧
      Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) ∧
      AnalyticOn ℂ (h a) (Metric.ball a (R a)) ∧
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    ∀ a ∈ T, ∀ z ∈ Metric.ball a (R a) \ {a},
      h a z - ∑ b ∈ T.erase a, P b z = f z - ∑ b ∈ T, P b z := by
  intro a haT z hzball
  obtain ⟨_, _, _, _, _, _, hfz⟩ := hper a haT
  have hfz' := hfz z hzball
  have hsum : ∑ b ∈ T, P b z = P a z + ∑ b ∈ T.erase a, P b z := by
    rw [← Finset.add_sum_erase _ _ haT]
  simp only [hfz', hsum]; ring

/-- For each pole `a ∈ T`, there exists a function `g_a : ℂ → ℂ` analytic on
`Metric.ball a (R a)` that agrees with `f - ∑ b ∈ T, P b` on the punctured ball
`Metric.ball a (R a) \ {a}`.

The witness is `g_a z = h a z - ∑ b ∈ T.erase a, P b z`. Analyticity follows from
`analyticOn_ball_sub_sum_erase` and the pointwise identity from
`sub_sum_erase_eq_sub_sum_punctured_ball`. -/
theorem exists_analyticOn_ball_eq_sub_sum
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
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    ∀ a ∈ T, ∃ (g_a : ℂ → ℂ),
      AnalyticOn ℂ g_a (Metric.ball a (R a)) ∧
      ∀ z ∈ Metric.ball a (R a) \ {a}, g_a z = f z - ∑ b ∈ T, P b z := by
  intro a ha
  have h_analytic :=
    analyticOn_ball_sub_sum_erase hU hT hf hγ hmaps P R h hper a ha
  have h_identity :=
    sub_sum_erase_eq_sub_sum_punctured_ball hU hT hf hγ hmaps P R h hper a ha
  exact ⟨fun z => h a z - ∑ b ∈ T.erase a, P b z, h_analytic, h_identity⟩

/-- **Pole gluing**: given a meromorphic function `f` on an open set `U ⊆ ℂ` with a finite set
of poles `T`, and principal parts `P a` at each pole `a ∈ T`, there exists a globally analytic
function `g : ℂ → ℂ` on `U` such that `f z = g z + ∑ a ∈ T, P a z` for all `z ∈ U \ ↑T`.

The proof has three steps:
1. `analyticOn_sub_sum_sdiff`: `f - ∑ P a` is analytic on `U \ T`.
2. `exists_analyticOn_ball_eq_sub_sum`: for each pole, a local analytic extension exists on
   `Metric.ball a (R a)` (concretely `h a - ∑ b ∈ T.erase a, P b`).
3. `exists_analyticOn_of_local_extensions`: the local extensions glue into a global analytic `g`
   on `U`; the identity `f z = g z + ∑ P a z` then follows by `ring`. -/
theorem exists_analyticOn_eq_add_sum
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
      (∀ z ∈ Metric.ball a (R a) \ {a}, f z = h a z + P a z)) :
    ∃ (g : ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) := by
  have h_F_anal : AnalyticOn ℂ (fun z => f z - ∑ a ∈ T, P a z) (U \ ↑T) :=
    analyticOn_sub_sum_sdiff hU hT hf hγ hmaps P R h hper
  have h_loc : ∀ a ∈ T, ∃ (g_a : ℂ → ℂ),
      AnalyticOn ℂ g_a (Metric.ball a (R a)) ∧
      ∀ z ∈ Metric.ball a (R a) \ {a}, g_a z = f z - ∑ b ∈ T, P b z :=
    exists_analyticOn_ball_eq_sub_sum hU hT hf hγ hmaps P R h hper
  have h_glue : ∃ (g : ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ z ∈ U \ ↑T, g z = f z - ∑ a ∈ T, P a z) :=
    exists_analyticOn_of_local_extensions hU hT hf hγ hmaps P R h hper h_F_anal h_loc
  obtain ⟨g, hg_anal, hg_pw⟩ := h_glue
  refine ⟨g, hg_anal, ?_⟩
  intro z hz
  have h_eq : g z = f z - ∑ a ∈ T, P a z := hg_pw z hz
  rw [h_eq]
  ring

end Library.Analysis.ResidueTheorem.PoleGluing
