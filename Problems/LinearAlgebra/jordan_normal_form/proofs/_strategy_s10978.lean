import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

theorem s10978
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (bU : Module.Basis (Fin (Module.finrank K (LinearMap.range N))) K (LinearMap.range N))
    (hbU : ∀ j : Fin (Module.finrank K (LinearMap.range N)),
        (N.restrict h_inv) (bU j) = 0 ∨
          ∃ i : Fin (Module.finrank K (LinearMap.range N)),
            (i : ℕ) + 1 = (j : ℕ) ∧ (N.restrict h_inv) (bU j) = bU i)
    (p : ℕ) (l : Fin p → ℕ)
    (e : Fin (Module.finrank K (LinearMap.range N)) ≃ Σ t : Fin p, Fin (l t))
    (o : Fin p → ℕ)
    (hoff : ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        (q : ℕ) = o (e q).1 + ((e q).2 : ℕ))
    (halign : ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        ((N.restrict h_inv) (bU q) = 0 ↔ ((e q).2 : ℕ) = 0)) :
    ∃ (p : ℕ) (l : Fin p → ℕ)
      (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N)),
      ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
      (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩ := by
  refine ⟨p, l, bU.reindex e, ?_⟩
  intro t j
  have heq : e (e.symm ⟨t, j⟩) = ⟨t, j⟩ := e.apply_symm_apply _
  have hreq : (bU.reindex e) ⟨t, j⟩ = bU (e.symm ⟨t, j⟩) := bU.reindex_apply e _
  have hoffj := hoff (e.symm ⟨t, j⟩)
  rw [heq] at hoffj
  dsimp only at hoffj
  rcases hbU (e.symm ⟨t, j⟩) with hzero | ⟨i, hi1, hi2⟩
  · left
    have hj0 := (halign (e.symm ⟨t, j⟩)).mp hzero
    rw [heq] at hj0
    dsimp only at hj0
    exact ⟨hj0, by rw [hreq]; exact hzero⟩
  · right
    have hjpos : (j : ℕ) ≠ 0 := by
      intro h0
      have hz : (N.restrict h_inv) (bU (e.symm ⟨t, j⟩)) = 0 := by
        apply (halign (e.symm ⟨t, j⟩)).mpr
        rw [heq]; dsimp only; exact h0
      rw [hi2] at hz
      exact bU.ne_zero i hz
    have hlt : (j : ℕ) - 1 < l t := by omega
    refine ⟨⟨(j : ℕ) - 1, hlt⟩, ?_, ?_⟩
    · change (j : ℕ) - 1 + 1 = (j : ℕ); omega
    · have hidx : i = e.symm ⟨t, ⟨(j : ℕ) - 1, hlt⟩⟩ := by
        apply Fin.ext
        have hoffi := hoff (e.symm ⟨t, ⟨(j : ℕ) - 1, hlt⟩⟩)
        rw [e.apply_symm_apply] at hoffi
        dsimp only at hoffi
        omega
      rw [hreq, hi2, bU.reindex_apply, hidx]


end Problems.LinearAlgebra.jordan_normal_form
