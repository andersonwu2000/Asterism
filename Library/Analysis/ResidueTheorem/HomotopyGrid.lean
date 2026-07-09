import Mathlib.AlgebraicTopology.FundamentalGroupoid.SimplyConnected
import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Calculus.ContDiff.Defs
import Mathlib.Analysis.InnerProductSpace.Basic

namespace Library.Analysis.ResidueTheorem.HomotopyGrid

/-!
# Homotopy grid lemmas for the residue theorem

This file provides the analytic backbone for reducing a closed-curve integral
in a simply-connected open set $U \subseteq \mathbb{C}$ to a finite grid sum.

## Main statements

* `simply_connected_continuous_null_homotopy_of_loop` — a $C^1$ loop in a simply-connected
  open set $U$ admits a continuous null-homotopy $H : [0,1]^2 \to U$.
* `homotopy_uniform_thickening` — the image of a continuous homotopy on the unit square
  is compactly contained in $U$, yielding a uniform ball radius $\delta > 0$.
* `homotopy_modulus_grid` — by Heine–Cantor, a continuous homotopy on the unit square has
  a modulus of continuity; Archimedean choice gives an $N \times N$ grid fine enough
  that each cell has $H$-diameter less than any prescribed $\varepsilon > 0$.
* `homotopy_lebesgue_grid` — combines the two preceding lemmas to cover the unit square
  by an $N \times N$ grid of balls, each contained in $U$, with every homotopy value
  belonging to the ball centred at the corresponding grid point.
-/

/-- A $C^1$ loop $\gamma : [0,1] \to U$ in a simply-connected open set `U ⊆ ℂ` admits a
continuous null-homotopy $H : [0,1]^2 \to U$.

The homotopy satisfies $H(0, t) = \gamma(t)$, $H(1, t) = \gamma(0)$ for all $t$, and
$H(\tau, 0) = H(\tau, 1) = \gamma(0)$ for all $\tau$, with every value in $U$.

The proof lifts $\gamma$ to a `Path` in $U$ and applies
`isSimplyConnected_iff_exists_homotopy_refl_forall_mem`, then reparametrises the resulting
`Path.Homotopy` via `Set.projIcc` to obtain $H : \mathbb{R} \to \mathbb{R} \to \mathbb{C}$. -/
theorem simply_connected_continuous_null_homotopy_of_loop
    {U : Set ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (hSC : SimplyConnectedSpace ↥U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U)
    (hclosed : γ 0 = γ 1) :
    ∃ H : ℝ → ℝ → ℂ,
      ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ∧
      (∀ t ∈ Set.Icc (0:ℝ) 1, H 0 t = γ t) ∧
      (∀ t ∈ Set.Icc (0:ℝ) 1, H 1 t = γ 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = γ 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = γ 0) ∧
      (∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) := by
  have hγ_cont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  let p_fun : unitInterval → ℂ := fun t => γ (t : ℝ)
  have p_cont : Continuous p_fun := by
    refine hγ_cont.comp_continuous continuous_subtype_val ?_
    intro t; exact t.2
  let p : Path (γ 0) (γ 0) :=
    { toFun := p_fun
      continuous_toFun := p_cont
      source' := rfl
      target' := by change γ 1 = γ 0; exact hclosed.symm }
  have hpU : ∀ t : unitInterval, p t ∈ U := fun t => hmaps t.2
  have hSC' : IsSimplyConnected U := hSC
  rcases (isSimplyConnected_iff_exists_homotopy_refl_forall_mem.mp hSC').2 (γ 0) p hpU
    with ⟨F, hFU⟩
  refine ⟨fun τ t =>
      F (Set.projIcc 0 1 zero_le_one τ, Set.projIcc 0 1 zero_le_one t),
    ?_, ?_, ?_, ?_, ?_, ?_⟩
  · have hF_cont : Continuous (fun p : unitInterval × unitInterval => F p) := F.continuous
    have : Continuous (fun p : ℝ × ℝ =>
        F (Set.projIcc 0 1 zero_le_one p.1, Set.projIcc 0 1 zero_le_one p.2)) :=
      hF_cont.comp ((continuous_projIcc.comp continuous_fst).prodMk
        (continuous_projIcc.comp continuous_snd))
    exact this.continuousOn
  · intro t ht
    change F (Set.projIcc 0 1 zero_le_one 0, Set.projIcc 0 1 zero_le_one t) = γ t
    rw [Set.projIcc_of_mem _ (Set.left_mem_Icc.mpr zero_le_one),
        Set.projIcc_of_mem _ ht]
    have h1 : F (⟨0, Set.left_mem_Icc.mpr zero_le_one⟩, ⟨t, ht⟩) = p ⟨t, ht⟩ := by
      have := F.toHomotopy.apply_zero ⟨t, ht⟩
      convert this
    rw [h1]; rfl
  · intro t ht
    change F (Set.projIcc 0 1 zero_le_one 1, Set.projIcc 0 1 zero_le_one t) = γ 0
    rw [Set.projIcc_of_mem _ (Set.right_mem_Icc.mpr zero_le_one),
        Set.projIcc_of_mem _ ht]
    have h1 : F (⟨1, Set.right_mem_Icc.mpr zero_le_one⟩, ⟨t, ht⟩) =
        (Path.refl (γ 0)) ⟨t, ht⟩ := by
      have := F.toHomotopy.apply_one ⟨t, ht⟩
      convert this
    rw [h1]; rfl
  · intro τ hτ
    change F (Set.projIcc 0 1 zero_le_one τ, Set.projIcc 0 1 zero_le_one 0) = γ 0
    rw [Set.projIcc_of_mem _ (Set.left_mem_Icc.mpr zero_le_one)]
    rw [Set.projIcc_of_mem _ hτ]
    have := Path.Homotopy.source F ⟨τ, hτ⟩
    convert this
  · intro τ hτ
    change F (Set.projIcc 0 1 zero_le_one τ, Set.projIcc 0 1 zero_le_one 1) = γ 0
    rw [Set.projIcc_of_mem _ (Set.right_mem_Icc.mpr zero_le_one)]
    rw [Set.projIcc_of_mem _ hτ]
    have := Path.Homotopy.target F ⟨τ, hτ⟩
    convert this
  · intro τ hτ t ht
    change F (Set.projIcc 0 1 zero_le_one τ, Set.projIcc 0 1 zero_le_one t) ∈ U
    exact hFU _

/-- The image of a continuous homotopy $H : [0,1]^2 \to U$ is compactly contained in the
open set `U`, so there exists a uniform $\delta > 0$ such that every ball
`Metric.ball (H τ t) δ` is contained in `U`. -/
theorem homotopy_uniform_thickening
    {U : Set ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U) :
    ∃ δ : ℝ, 0 < δ ∧
      ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
        Metric.ball (H τ t) δ ⊆ U := by
  have hK : IsCompact (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    isCompact_Icc.prod isCompact_Icc
  have hKim : IsCompact ((Function.uncurry H) '' (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) :=
    hK.image_of_continuousOn hHcont
  have hKU : (Function.uncurry H) '' (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ⊆ U := by
    rintro z ⟨⟨τ, t⟩, ⟨hτ, ht⟩, rfl⟩
    exact hHmaps τ hτ t ht
  obtain ⟨δ, hδ, hthick⟩ := hKim.exists_thickening_subset_open hU hKU
  refine ⟨δ, hδ, fun τ hτ t ht z hz => hthick ?_⟩
  have hHτt : H τ t ∈ (Function.uncurry H) '' (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    ⟨(τ, t), Set.mk_mem_prod hτ ht, rfl⟩
  rw [Metric.mem_thickening_iff]
  exact ⟨H τ t, hHτt, Metric.mem_ball.mp hz⟩

/-- Given $\varepsilon > 0$ and a continuous homotopy $H : [0,1]^2 \to \mathbb{C}$, there
exists $N : \mathbb{N}$ with $N > 0$ such that for every $N \times N$ grid cell
$[i/N, (i+1)/N] \times [j/N, (j+1)/N]$, all values $H(\tau, t)$ in that cell satisfy
$\operatorname{dist}(H(\tau, t), H(i/N, j/N)) < \varepsilon$.

This follows from Heine–Cantor (uniform continuity of $H$ on the compact unit square)
and the Archimedean property to choose $N$ fine enough. -/
theorem homotopy_modulus_grid
    {H : ℝ → ℝ → ℂ}
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (ε : ℝ) (hε : 0 < ε) :
    ∃ N : ℕ, 0 < N ∧
      ∀ i j, i < N → j < N →
        ∀ τ ∈ Set.Icc ((i:ℝ)/N) (((i:ℝ)+1)/N),
        ∀ t ∈ Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N),
          dist (H τ t) (H ((i:ℝ)/N) ((j:ℝ)/N)) < ε := by
  have hS : IsCompact (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1) :=
    isCompact_Icc.prod isCompact_Icc
  have hunif := hS.uniformContinuousOn_of_continuous hHcont
  rw [Metric.uniformContinuousOn_iff] at hunif
  obtain ⟨δ, hδ, hunif⟩ := hunif ε hε
  obtain ⟨m, hm⟩ := exists_nat_one_div_lt hδ
  refine ⟨m + 1, Nat.succ_pos m, fun i j hi hj τ hτ t ht => ?_⟩
  have hN : (0 : ℝ) < (m : ℝ) + 1 := by positivity
  push_cast at hτ ht ⊢
  have gridBnd : ∀ {k : ℕ} {s : ℝ}, k < m + 1 →
      s ∈ Set.Icc ((k : ℝ) / ((m : ℝ) + 1)) (((k : ℝ) + 1) / ((m : ℝ) + 1)) →
      s ∈ Set.Icc (0 : ℝ) 1 ∧ dist s ((k : ℝ) / ((m : ℝ) + 1)) < δ := by
    intro k s hk hs
    have htop : ((k : ℝ) + 1) / ((m : ℝ) + 1) ≤ 1 := by rw [div_le_one hN]; norm_cast
    constructor
    · exact ⟨le_trans (by positivity) hs.1, le_trans hs.2 htop⟩
    · rw [Real.dist_eq]
      apply lt_of_le_of_lt _ hm
      rw [abs_le]
      have heq : ((k : ℝ) + 1) / ((m : ℝ) + 1) =
          (k : ℝ) / ((m : ℝ) + 1) + 1 / ((m : ℝ) + 1) := by
        field_simp
      exact ⟨by linarith [hs.1, div_pos one_pos hN], by linarith [hs.2, heq]⟩
  obtain ⟨hτ_unit, hτ_dist⟩ := gridBnd hi hτ
  obtain ⟨ht_unit, ht_dist⟩ := gridBnd hj ht
  have hτ_mem : (τ, t) ∈ Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1 := ⟨hτ_unit, ht_unit⟩
  have hpt_mem : ((i : ℝ) / ((m : ℝ) + 1), (j : ℝ) / ((m : ℝ) + 1)) ∈
      Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1 := by
    refine ⟨⟨by positivity, ?_⟩, by positivity, ?_⟩ <;> (rw [div_le_one hN]; norm_cast; omega)
  have hdist : dist (τ, t) ((i : ℝ) / ((m : ℝ) + 1), (j : ℝ) / ((m : ℝ) + 1)) < δ := by
    rw [Prod.dist_eq]; exact max_lt hτ_dist ht_dist
  simpa [Function.uncurry] using hunif (τ, t) hτ_mem _ hpt_mem hdist

/-- **Lebesgue grid lemma**: for a continuous homotopy $H : [0,1]^2 \to U$ into an open set
`U ⊆ ℂ`, there exists $N > 0$ and functions $c : \mathbb{N} \to \mathbb{N} \to \mathbb{C}$
and $r : \mathbb{N} \to \mathbb{N} \to \mathbb{R}$ such that for every grid cell
$(i, j)$ with $i, j < N$:
- $r(i,j) > 0$ and `Metric.ball (c i j) (r i j) ⊆ U`,
- every $H(\tau, t)$ with $(\tau, t) \in [i/N,(i+1)/N] \times [j/N,(j+1)/N]$
  lies in `Metric.ball (c i j) (r i j)`.

The proof combines `homotopy_uniform_thickening` (a uniform $\delta > 0$ with
`ball (H τ t) δ ⊆ U`) and `homotopy_modulus_grid` (choosing $N$ so that each cell
has $H$-diameter less than $\delta$), taking $c(i,j) := H(i/N, j/N)$ and $r(i,j) := \delta$. -/
theorem homotopy_lebesgue_grid
    {U : Set ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0 : ℝ) 1 ×ˢ Set.Icc (0 : ℝ) 1))
    (hHmaps : ∀ τ ∈ Set.Icc (0 : ℝ) 1, ∀ t ∈ Set.Icc (0 : ℝ) 1, H τ t ∈ U) :
    ∃ N : ℕ, 0 < N ∧ ∃ c : ℕ → ℕ → ℂ, ∃ r : ℕ → ℕ → ℝ,
      ∀ i j, i < N → j < N →
        0 < r i j ∧ Metric.ball (c i j) (r i j) ⊆ U ∧
          (∀ τ ∈ Set.Icc ((i:ℝ)/N) (((i:ℝ)+1)/N),
            ∀ t ∈ Set.Icc ((j:ℝ)/N) (((j:ℝ)+1)/N),
              H τ t ∈ Metric.ball (c i j) (r i j)) := by
  obtain ⟨δ, hδpos, hδball⟩ :=
    homotopy_uniform_thickening (U := U) (H := H) hU hHcont hHmaps
  obtain ⟨N, hNpos, hgrid⟩ :=
    homotopy_modulus_grid (H := H) hHcont δ hδpos
  refine ⟨N, hNpos, (fun i j => H ((i:ℝ)/N) ((j:ℝ)/N)), (fun _ _ => δ), ?_⟩
  intro i j hi hj
  have hNposR : (0 : ℝ) < (N : ℝ) := by exact_mod_cast hNpos
  have hiN : ((i:ℝ)/N) ∈ Set.Icc (0:ℝ) 1 := by
    refine ⟨div_nonneg (by exact_mod_cast Nat.zero_le i) hNposR.le, ?_⟩
    rw [div_le_one hNposR]; exact_mod_cast hi.le
  have hjN : ((j:ℝ)/N) ∈ Set.Icc (0:ℝ) 1 := by
    refine ⟨div_nonneg (by exact_mod_cast Nat.zero_le j) hNposR.le, ?_⟩
    rw [div_le_one hNposR]; exact_mod_cast hj.le
  refine ⟨hδpos, hδball ((i:ℝ)/N) hiN ((j:ℝ)/N) hjN, ?_⟩
  intro τ hτ t ht
  exact Metric.mem_ball.mpr (hgrid i j hi hj τ hτ t ht)

end Library.Analysis.ResidueTheorem.HomotopyGrid
