import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- family_chain_strong: Jordan chain relation for each block with strong hd (j=0 on zero branch)
-- Identical structure to family_chain; the strong hd's extra conjunct is destructured and discarded.
-- entry_kind: Builder
theorem family_chain_strong
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W)) :
    ∀ (s : ({t : Fin p // 0 < l t} ⊕ Fin m))
      (j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)),
        N (v ⟨s, j⟩) = 0 ∨
          ∃ i : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s),
            (i : ℕ) + 1 = (j : ℕ) ∧ N (v ⟨s, j⟩) = v ⟨s, i⟩ := by
  intro s j
  rcases s with ⟨t, ht⟩ | c
  · -- Sum.inl ⟨t, ht⟩: chain block, t : Fin p, ht : 0 < l t, j : Fin (l t + 1)
    induction j using Fin.lastCases with
    | last =>
      -- j = Fin.last (l t): top element, N maps it to d ⟨t, l t - 1⟩ via hx
      right
      refine ⟨(⟨l t - 1, by omega⟩ : Fin (l t)).castSucc, ?_, ?_⟩
      · simp [Fin.val_last]; omega
      · rw [hv_top ⟨t, ht⟩, hx t ⟨l t - 1, by omega⟩,
            ← hv_chain ⟨t, ht⟩ ⟨l t - 1, Nat.sub_lt ht Nat.one_pos⟩]
    | cast i =>
      -- j = i.castSucc: inner chain element, use hd t i (strong form)
      rw [hv_chain ⟨t, ht⟩ i]
      rcases hd t i with ⟨_, h0⟩ | ⟨i', hi'_eq, hi'_val⟩
      · left
        simp only [LinearMap.restrict_apply] at h0
        exact congr_arg Subtype.val h0
      · right
        have hval : N (↑(d ⟨t, i⟩) : W) = ↑(d ⟨t, i'⟩) := by
          simp only [LinearMap.restrict_apply] at hi'_val
          exact congr_arg Subtype.val hi'_val
        refine ⟨i'.castSucc, ?_, ?_⟩
        · simp only [Fin.val_castSucc]; omega
        · rw [hval, ← hv_chain ⟨t, ht⟩ i']
  · -- Sum.inr c: complement basis, block of length 1
    simp only [Sum.elim_inr]
    left
    have hj : j = (0 : Fin 1) := Fin.eq_zero j
    subst hj
    rw [hv_C c]
    exact LinearMap.mem_ker.mp (hC1 (Submodule.coe_mem (cb c)))

