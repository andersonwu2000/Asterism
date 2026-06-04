import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.l_block_enum_consecutive

namespace Problems.LinearAlgebra.jordan_normal_form

-- Reindex via block_enum_consecutive + cardinality bridge.
-- block_enum_consecutive (proved brick s10915) gives e : Fin (∑ k s) ≃ Σ s, Fin (k s).
-- finrank K W = ∑ k s from basis c; finCongr then closes Fin (finrank W) ≃ Fin (∑ k s).
-- Compose: φ := finCongr.trans e gives Fin (finrank W) ≃ Σ s, Fin (k s); reindex c via φ.
theorem s11023
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (r : ℕ) (k : Fin r → ℕ)
    (c : Module.Basis (Σ s : Fin r, Fin (k s)) K W)
    (hc : ∀ (s : Fin r) (j : Fin (k s)),
        N (c ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (k s), (i : ℕ) + 1 = (j : ℕ) ∧ N (c ⟨s, j⟩) = c ⟨s, i⟩) :
    ∃ b : Module.Basis (Fin (Module.finrank K W)) K W,
      ∀ j : Fin (Module.finrank K W),
        N (b j) = 0 ∨
          ∃ i : Fin (Module.finrank K W),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (b j) = b i  := by
  obtain ⟨e, he⟩ := block_enum_consecutive k
  have h_card : Module.finrank K W = ∑ s, k s := by
    rw [Module.finrank_eq_card_basis c, Fintype.card_sigma]
    simp [Fintype.card_fin]
  let φ : Fin (Module.finrank K W) ≃ Σ s : Fin r, Fin (k s) :=
    (finCongr h_card).trans e
  refine ⟨c.reindex φ.symm, ?_⟩
  intro j
  have hbj : (c.reindex φ.symm) j = c (φ j) := by
    simp [Module.Basis.reindex_apply]
  rcases hc (φ j).1 (φ j).2 with h0 | ⟨i, hi_eq, hi_N⟩
  · left
    rw [hbj]
    have heq : (⟨(φ j).1, (φ j).2⟩ : Σ s : Fin r, Fin (k s)) = φ j := rfl
    rw [heq] at h0
    exact h0
  · right
    refine ⟨φ.symm ⟨(φ j).1, i⟩, ?_, ?_⟩
    · set p := φ.symm ⟨(φ j).1, i⟩ with hp
      have hφp : φ p = ⟨(φ j).1, i⟩ := by simp [hp]
      have h_fst : (φ p).1 = (φ j).1 := by rw [hφp]
      have h_snd_p : ((φ p).2 : ℕ) = (i : ℕ) := by rw [hφp]
      have hep : φ p = e ((finCongr h_card) p) := rfl
      have hej : φ j = e ((finCongr h_card) j) := rfl
      have h_fst' : (e ((finCongr h_card) p)).1 = (e ((finCongr h_card) j)).1 := by
        rw [← hep, ← hej]; exact h_fst
      have hiff := he ((finCongr h_card) p) ((finCongr h_card) j) h_fst'
      have h_lhs : ((e ((finCongr h_card) p)).2 : ℕ) + 1 = ((e ((finCongr h_card) j)).2 : ℕ) := by
        rw [← hep, ← hej]
        rw [h_snd_p]; exact hi_eq
      have h_pj : ((finCongr h_card) p : ℕ) + 1 = ((finCongr h_card) j : ℕ) := hiff.mp h_lhs
      simpa using h_pj
    · rw [hbj]
      have hbp : (c.reindex φ.symm) (φ.symm ⟨(φ j).1, i⟩) = c ⟨(φ j).1, i⟩ := by
        rw [Module.Basis.reindex_apply]; simp
      rw [hbp]
      have heq : (⟨(φ j).1, (φ j).2⟩ : Σ s : Fin r, Fin (k s)) = φ j := rfl
      rw [heq] at hi_N
      exact hi_N

end Problems.LinearAlgebra.jordan_normal_form
