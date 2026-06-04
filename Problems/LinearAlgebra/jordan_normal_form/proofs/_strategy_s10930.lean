import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- Direct proof (leaf): reindex the flat consecutive Jordan basis `bU` of `range N` by the
-- layout equiv `e`, taking `d := bU.reindex e` (so `d ⟨t,j⟩ = bU (e.symm ⟨t,j⟩)`).
-- Per block-index `(t,j)`, set `q := e.symm ⟨t,j⟩`; `h_off`+`heq` give `(q:ℕ) = o t + j`.
-- Case-split `hbU q`: the zero case is the left disjunct directly; otherwise `hbU` yields a
-- flat predecessor `i₀` with `(i₀:ℕ)+1 = (q:ℕ)`, and `h_align` forces `j ≠ 0`. The chain
-- partner `⟨j-1, _⟩` reindexes to `q' := e.symm ⟨t,⟨j-1⟩⟩` whose offset value (via `h_off`)
-- matches `i₀` numerically, so `Fin.ext`+`omega` gives `i₀ = q'`, closing `N(d⟨t,j⟩) = d⟨t,⟨j-1⟩⟩`.
theorem s10930
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
    (h_off : ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        (q : ℕ) = o (e q).1 + ((e q).2 : ℕ))
    (h_align : ∀ q : Fin (Module.finrank K (LinearMap.range N)),
        ((N.restrict h_inv) (bU q) = 0 ↔ ((e q).2 : ℕ) = 0)) :
    ∃ (p : ℕ) (l : Fin p → ℕ)
      (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N)),
      ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩  := by
  refine ⟨p, l, bU.reindex e, ?_⟩
  intro t j
  have heq : e (e.symm ⟨t, j⟩) = ⟨t, j⟩ := e.apply_symm_apply _
  have hqval : ((e.symm ⟨t, j⟩ : Fin _) : ℕ) = o t + (j : ℕ) := by
    have := h_off (e.symm ⟨t, j⟩)
    rw [heq] at this
    exact this
  rcases hbU (e.symm ⟨t, j⟩) with hzero | ⟨i₀, hi₀1, hi₀2⟩
  · left
    rw [Module.Basis.reindex_apply]
    exact hzero
  · right
    have hjne : (j : ℕ) ≠ 0 := by
      intro hj0
      have hz : (N.restrict h_inv) (bU (e.symm ⟨t, j⟩)) = 0 := by
        rw [h_align (e.symm ⟨t, j⟩), heq]
        exact hj0
      rw [hi₀2] at hz
      exact bU.ne_zero i₀ hz
    have hjp_lt : (j : ℕ) - 1 < l t := by omega
    refine ⟨⟨(j : ℕ) - 1, hjp_lt⟩, by simp; omega, ?_⟩
    rw [Module.Basis.reindex_apply, Module.Basis.reindex_apply]
    have heq' : e (e.symm ⟨t, ⟨(j : ℕ) - 1, hjp_lt⟩⟩) = ⟨t, ⟨(j : ℕ) - 1, hjp_lt⟩⟩ :=
      e.apply_symm_apply _
    have hq'val : ((e.symm ⟨t, ⟨(j : ℕ) - 1, hjp_lt⟩⟩ : Fin _) : ℕ) = o t + ((j : ℕ) - 1) := by
      have := h_off (e.symm ⟨t, ⟨(j : ℕ) - 1, hjp_lt⟩⟩)
      rw [heq'] at this
      exact this
    have hi0eq : i₀ = e.symm ⟨t, ⟨(j : ℕ) - 1, hjp_lt⟩⟩ := by
      apply Fin.ext
      omega
    rw [hi₀2, hi0eq]


end Problems.LinearAlgebra.jordan_normal_form
