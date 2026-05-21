import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct construction: lift γ to a Path in ℂ, then apply Mathlib's
-- `isSimplyConnected_iff_exists_homotopy_refl_forall_mem` to obtain a
-- `Path.Homotopy` to the constant loop with image in U. Reparametrize
-- via `Set.projIcc` from ℝ to `unitInterval` to extract H : ℝ → ℝ → ℂ.

theorem s10571
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
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
      (∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U)  := by
  have h0U : γ 0 ∈ U := hmaps (Set.left_mem_Icc.mpr zero_le_one)
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

end Problems.residue_thm
