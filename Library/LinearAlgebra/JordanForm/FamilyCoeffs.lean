import Mathlib

namespace Library.LinearAlgebra.JordanForm.FamilyCoeffs

-- Direct leaf: the d-relation `hrel` is a vanishing combo over distinct basis vectors.
-- `ti ↦ ⟨ti.1.1, ti.2⟩` injects the positive-length-chain index into `d`'s index, so the
-- coerced subfamily `↑(d ⟨ti.1.1, ti.2⟩)` is LI (d.linearIndependent.comp, then .map' through
-- the range-subtype with trivial kernel). `Fintype.linearIndependent_iff` reads off `hrel` to
-- force every coefficient `g ⟨Sum.inl ti.1, ti.2.succ⟩ = 0`. Sorry-free; no sub-goals.
theorem d_coeff_vanish
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (hrel : (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • (↑(d ⟨ti.1.1, ti.2⟩) : W)) = 0) :
    ∀ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
      g ⟨Sum.inl ti.1, ti.2.succ⟩ = 0  := by
  have h_li : LinearIndependent K (fun ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1) =>
      (↑(d ⟨ti.1.1, ti.2⟩) : W)) := by
    have hsub : LinearIndependent K (fun ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1) =>
        d ⟨ti.1.1, ti.2⟩) := by
      apply d.linearIndependent.comp
          (fun ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1) =>
            (⟨ti.1.1, ti.2⟩ : Σ t : Fin p, Fin (l t)))
      rintro ⟨⟨a, ha⟩, i⟩ ⟨⟨b, hb⟩, j⟩ hab
      simp only [Sigma.mk.inj_iff] at hab
      obtain ⟨h1, h2⟩ := hab
      subst h1
      simp_all
    exact hsub.map' (LinearMap.range N).subtype (Submodule.ker_subtype _)
  exact Fintype.linearIndependent_iff.mp h_li (fun ti => g ⟨Sum.inl ti.1, ti.2.succ⟩) hrel

-- Extract above-bottom coeff vanishing from the d-relation `hrel`, then index-translate.
-- `d_coeff_vanish`: LI of the injective subfamily `ti ↦ ↑(d ⟨ti.1.1, ti.2⟩)` of basis `d`
--   forces every coefficient `g ⟨inl ti.1, ti.2.succ⟩` in `hrel = 0` to vanish (succ-form).
-- Combinator: for `j : Fin (l t.1 + 1)` with `0 < j`, write `j = (j.pred).succ` and apply.
--   The sub-goal drops the `0 < j` hypothesis and the `Fin (l+1)` index gymnastics, stating
--   the result in the natural succ-indexed form matching `hrel`'s summands — strictly simpler.
theorem li_extract_above
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (hrel : (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • (↑(d ⟨ti.1.1, ti.2⟩) : W)) = 0) :
    ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0  := by
  have hcoeff := d_coeff_vanish N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg hrel
  intro t j hj
  obtain ⟨k, rfl⟩ : ∃ k : Fin (l t.1), k.succ = j :=
    ⟨j.pred (by rintro rfl; simp at hj), Fin.succ_pred j (by rintro rfl; simp at hj)⟩
  exact hcoeff ⟨t, k⟩

-- entry_kind: Builder
theorem n_distrib_smul_sum
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (N : W →ₗ[K] W)
    (p : ℕ) (l : Fin p → ℕ) (m : ℕ)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K) :
    N (∑ i, g i • v i) = ∑ i, g i • N (v i) := by norm_num

-- n_sum_collapse_to_inl_succ: collapses ∑ over all v-indices to inl-succ terms only;
-- inl-bottom terms vanish (chain-bottom maps to 0 via hd), inr terms vanish (C ≤ ker N).
-- entry_kind: Builder
theorem n_sum_collapse_to_inl_succ
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
               (fun _ : Fin m => 1) s)) → K) :
    (∑ i, g i • N (v i)) =
      (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • N (v ⟨Sum.inl ti.1, ti.2.succ⟩)) := by

  rw [Fintype.sum_sigma, Fintype.sum_sum_type]
  have h_inr : ∀ c : Fin m,
      (∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
                            (fun _ : Fin m => 1) (Sum.inr c)),
        g ⟨Sum.inr c, j⟩ • N (v ⟨Sum.inr c, j⟩)) = 0 := fun c => by
    simp only [Sum.elim_inr]
    have hker : N ((cb c : W)) = 0 :=
      LinearMap.mem_ker.mp (hC1 (Submodule.coe_mem _))
    simp [hv_C c, hker]
  simp_rw [h_inr, Finset.sum_const_zero, add_zero]
  have h_inl_bot : ∀ (t : {t : Fin p // 0 < l t}),
      N (v ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) = 0 := fun t => by
    have hlt : 0 < l t.1 := t.2
    have hj0 : (⟨0, hlt⟩ : Fin (l t.1)).castSucc = (0 : Fin (l t.1 + 1)) := by
      simp [Fin.castSucc]
    rw [← hj0, hv_chain t ⟨0, hlt⟩]
    have hd0 : (N.restrict h_inv) (d ⟨t.1, ⟨0, hlt⟩⟩) = 0 :=
      ((hd t.1 ⟨0, hlt⟩).resolve_right
        (fun ⟨i, hi, _⟩ => by simp at hi)).2
    have heq := LinearMap.restrict_apply h_inv (d ⟨t.1, ⟨0, hlt⟩⟩)
    rw [hd0] at heq
    simpa using heq.symm
  have h_inl_split : ∀ (t : {t : Fin p // 0 < l t}),
      (∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
                            (fun _ : Fin m => 1) (Sum.inl t)),
        g ⟨Sum.inl t, j⟩ • N (v ⟨Sum.inl t, j⟩)) =
      ∑ j : Fin (l t.1), g ⟨Sum.inl t, j.succ⟩ • N (v ⟨Sum.inl t, j.succ⟩) := fun t => by
    simp only [Sum.elim_inl]
    change ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • N (v ⟨Sum.inl t, j⟩) = _
    rw [Fin.sum_univ_succ]
    simp [h_inl_bot t]
  simp_rw [h_inl_split]
  rw [Fintype.sum_sigma]

-- n_v_inl_succ_eq_d: per-element chain shift using hv_chain/hv_top and hx/hd
-- entry_kind: Builder
theorem n_v_inl_succ_eq_d
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (N : W →ₗ[K] W)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (x : (Σ t : Fin p, Fin (l t)) → W)
    (hx : ∀ (t : Fin p) (j : Fin (l t)), N (x ⟨t, j⟩) = (↑(d ⟨t, j⟩) : W))
    (m : ℕ)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = (↑(d ⟨t.1, i⟩) : W))
    (hv_top : ∀ (t : {t : Fin p // 0 < l t}),
        v ⟨Sum.inl t, Fin.last (l t.1)⟩ = x ⟨t.1, ⟨l t.1 - 1, by have := t.2; omega⟩⟩) :
    ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1)),
        N (v ⟨Sum.inl t, j.succ⟩) = (↑(d ⟨t.1, j⟩) : W) := by
  intro t j
  by_cases hj : j.val + 1 = l t.1
  · -- j.succ = Fin.last (l t.1), and j = ⟨l t.1 - 1, _⟩
    have hlt1 : l t.1 - 1 < l t.1 := by omega
    have hjsucc : j.succ = Fin.last (l t.1) := by
      ext; simp [Fin.val_succ, Fin.val_last]; omega
    have hjval : j = ⟨l t.1 - 1, hlt1⟩ := by
      apply Fin.ext; show (j : ℕ) = l t.1 - 1; omega
    rw [hjsucc, hv_top, hjval]
    exact hx t.1 ⟨l t.1 - 1, hlt1⟩
  · -- j.val + 1 < l t.1, so j.succ = castSucc of ⟨j.val+1, _⟩
    have hlt : j.val + 1 < l t.1 := by omega
    have hj' : j.val + 1 < l t.1 := hlt
    set j' : Fin (l t.1) := ⟨j.val + 1, hlt⟩ with hj'_def
    have hjsucc : j.succ = j'.castSucc := by
      ext; simp [Fin.val_succ, Fin.val_castSucc, hj'_def]
    rw [hjsucc, hv_chain t j']
    -- goal: N (↑(d ⟨t.1, j'⟩)) = ↑(d ⟨t.1, j⟩)
    rcases hd t.1 j' with ⟨h0, _⟩ | ⟨i, hi_val, hi_eq⟩
    · -- j'.val = 0, contradicts j'.val = j.val + 1 ≥ 1
      simp [hj'_def] at h0
    · -- i.val + 1 = j'.val = j.val + 1, so i = j
      have hij : i = j := by
        ext; simp [hj'_def] at hi_val; omega
      rw [hij] at hi_eq
      -- hi_eq : N.restrict h_inv (d ⟨t.1, j'⟩) = d ⟨t.1, j⟩ in range N
      have hcoe : (↑((N.restrict h_inv) (d ⟨t.1, j'⟩)) : W) = N (↑(d ⟨t.1, j'⟩)) := by
        simp [LinearMap.restrict_apply]
      rw [← hcoe]
      exact congr_arg Subtype.val hi_eq

-- Mirror the abstract 3-step decomposition pattern: linearity → reindex/drop-zero → per-element shift.
-- (1) `n_distrib_smul_sum`: N distributes through `∑ g i • v i` into `∑ g i • N (v i)`.
-- (2) `n_sum_collapse_to_inl_succ`: drop vanishing inl-bottom and inr-bottom terms; reindex
--     surviving inl-succ terms to `Σ t, Fin (l t.1)`.
-- (3) `n_v_inl_succ_eq_d`: per-element chain shift `N (v ⟨inl t, j.succ⟩) = d ⟨t.1, j⟩`.
-- Combiner: rewrite by (1) and (2), then `Finset.sum_congr` applies (3) pointwise inside `g • _`.
theorem pushforward_d_eq_alias
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K) :
    N (∑ i, g i • v i) =
      (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • (↑(d ⟨ti.1.1, ti.2⟩) : W))  := by
  have h_lin := n_distrib_smul_sum N p l m v g
  have h_reindex := n_sum_collapse_to_inl_succ N hN h_inv p l d hd x hx
    C hC1 hC2 hC3 m cb v hv_chain hv_top hv_C g
  have h_chain := n_v_inl_succ_eq_d N h_inv p l d hd x hx m v hv_chain hv_top
  rw [h_lin, h_reindex]
  exact Finset.sum_congr rfl (fun ti _ => by rw [h_chain ti.1 ti.2])

-- Use the already-abstract `pushforward_d_eq` identity:
--   N (∑ gᵢ • vᵢ) = ∑_{ti} g⟨inl ti.1, ti.2.succ⟩ • d⟨ti.1.1, ti.2⟩
-- Then `hg : ∑ gᵢ • vᵢ = 0` collapses the LHS via `map_zero`, giving the goal.
theorem pushforward_d_relation
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0) :
    (∑ (ti : Σ t : {t : Fin p // 0 < l t}, Fin (l t.1)),
        g ⟨Sum.inl ti.1, ti.2.succ⟩ • (↑(d ⟨ti.1.1, ti.2⟩) : W)) = 0  := by
  have heq := pushforward_d_eq_alias N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g
  rw [← heq, hg, map_zero]

-- Above-bottom coeffs vanish: push `N` through the relation `hg : ∑ gᵢ • vᵢ = 0`.
-- `pushforward_d_relation` collapses `N (∑ gᵢ • vᵢ) = 0` to a combination of the range-basis
--   `d`: complement vectors and chain bottoms (j = 0) die under `N`, while each interior/top
--   shifts down to `d⟨t, j-1⟩`, leaving `∑_{t,i} g⟨inl t, i.succ⟩ • d⟨t,i⟩ = 0`.
-- `li_extract_above` then runs `d`'s linear independence on that relation to force every
--   above-bottom coefficient `g⟨inl t, j⟩` (j ≥ 1) to 0. Each phase drops the other's work
--   (phase 1 needs no LI; phase 2 needs no `N`-pushforward), so both are strictly simpler.
theorem above_bottom_vanish
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0) :
    ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0  := by
  have h_rel := pushforward_d_relation N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg
  exact li_extract_above N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg h_rel

-- Direct leaf (no sub-goals): the chain bottoms `↑(d ⟨t.1, ⟨0, t.2⟩⟩)` are an injective
-- subfamily of the Jordan basis `d`, so they are LI in `range N` (d.linearIndependent.comp
-- on the injection `t ↦ ⟨t.1, ⟨0, t.2⟩⟩`), then LI in W after lifting through the range
-- subtype (.map' with trivial kernel). `Fintype.linearIndependent_iff` reads `hzero` off to
-- force every bottom coeff `g ⟨Sum.inl t, 0⟩ = 0`. Sorry-free; ships alone for leaf-bypass.
theorem chain_bottom_coeffs_of_sum_zero
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0)
    (hzero : (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) = 0) :
    ∀ (t : {t : Fin p // 0 < l t}), g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0  := by
  have h_li : LinearIndependent K
      (fun t : {t : Fin p // 0 < l t} => (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) := by
    have hsub : LinearIndependent K
        (fun t : {t : Fin p // 0 < l t} => d ⟨t.1, ⟨0, t.2⟩⟩) := by
      apply d.linearIndependent.comp
          (fun t : {t : Fin p // 0 < l t} => (⟨t.1, ⟨0, t.2⟩⟩ : Σ t : Fin p, Fin (l t)))
      intro a b hab
      simp only [Sigma.mk.inj_iff] at hab
      exact Subtype.ext hab.1
    exact hsub.map' (LinearMap.range N).subtype (Submodule.ker_subtype _)
  exact Fintype.linearIndependent_iff.mp h_li
    (fun t => g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩) hzero

theorem chain_bottom_range_part_zero
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0)
    (hres : (∑ t : {t : Fin p // 0 < l t},
          g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
        + (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W)) = 0) :
    (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) = 0  := by
  have hA : (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) ∈ LinearMap.range N :=
    Submodule.sum_mem _ (fun t _ => Submodule.smul_mem _ _ (Submodule.coe_mem (d ⟨t.1, ⟨0, t.2⟩⟩)))
  have hB : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W)) ∈ C :=
    Submodule.sum_mem _ (fun c _ => Submodule.smul_mem _ _ (Submodule.coe_mem (cb c)))
  set A := ∑ t : {t : Fin p // 0 < l t},
      g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W) with hAdef
  set B := ∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W) with hBdef
  have hAC : A ∈ C := by
    have hAB : A = -B := by rw [eq_neg_iff_add_eq_zero]; exact hres
    rw [hAB]; exact Submodule.neg_mem C hB
  exact Submodule.disjoint_def.mp hC2 A hAC hA

-- Direct leaf: the residual is exactly the `hg` dependence after the `habove` collapse.
-- Split `∑ i` over the Σ/⊕ index (`Finset.sum_sigma` + `Fintype.sum_sum_type`) into the
-- `Sum.inl` chain block and `Sum.inr` complement block. On each `inl` fiber `Fin.sum_univ_succ`
-- isolates `j=0`; `habove` zeroes every `j≥1` term and `hv_chain` (at `i=⟨0,t.2⟩`, whose
-- `castSucc` is `0`) rewrites the survivor to `g⟨inl t,0⟩ • d⟨t.1,0⟩`. Each `inr` fiber is
-- `Fin 1`, so `Fin.sum_univ_one` + `hv_C` give `g⟨inr c,0⟩ • cb c`. Sorry-free; no sub-goals.
theorem chain_bottom_residual
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
      + (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W)) = 0  := by
  have hsplit :
      (∑ i, g i • v i)
        = (∑ t : {t : Fin p // 0 < l t},
              ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩)
          + (∑ c : Fin m, ∑ j : Fin 1, g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩) := by
    rw [← Finset.univ_sigma_univ, Finset.sum_sigma, Fintype.sum_sum_type]
    rfl
  have hinl :
      (∑ t : {t : Fin p // 0 < l t},
          ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩)
        = ∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W) := by
    apply Finset.sum_congr rfl
    intro t _
    rw [Fin.sum_univ_succ,
      Finset.sum_eq_zero (fun j _ => by rw [habove t j.succ (by simp), zero_smul]), add_zero]
    congr 1
    exact hv_chain t ⟨0, t.2⟩
  have hinr :
      (∑ c : Fin m, ∑ j : Fin 1, g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩)
        = ∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W) := by
    apply Finset.sum_congr rfl
    intro c _
    rw [Fin.sum_univ_one]
    congr 1
    exact hv_C c
  rw [← hinl, ← hinr, ← hsplit]
  exact hg

-- Bottom-coeff vanishing for the chain part of the assembled Jordan family.
-- After `habove` kills every above-bottom coeff, the dependence `hg` collapses to a pure
-- bottom relation `(∑_t g⟨inl t,0⟩ • d⟨t.1,0⟩) + (∑_c g⟨inr c,0⟩ • cb c) = 0` (`chain_bottom_residual`).
-- The first sum lies in `range N`, the second in `C`; `hC2`-disjointness forces the
-- `range N` part to vanish (`chain_bottom_range_part_zero`). Linear independence of the chain
-- bottoms (`chain_bottoms_li`, lifted along `range N ↪ W`) then forces each chain-bottom coeff
-- to 0 (`chain_bottom_coeffs_of_sum_zero`). Combinator threads h_res → h_zero → conclusion.
-- Each sub-goal is strictly simpler: #1 is the sum reduction alone, #2 assumes that relation and
-- only runs disjointness, #3 assumes the range part is 0 and only runs the LI argument.
theorem chain_bottom_coeffs
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    ∀ (t : {t : Fin p // 0 < l t}), g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ = 0  := by
  have h_res :
      (∑ t : {t : Fin p // 0 < l t},
          g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
        + (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (↑(cb c) : W)) = 0 :=
    chain_bottom_residual N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove
  have h_zero :
      (∑ t : {t : Fin p // 0 < l t},
          g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) = 0 :=
    chain_bottom_range_part_zero N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove h_res
  exact chain_bottom_coeffs_of_sum_zero N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove h_zero

-- sum_bookkeeping_abstract: pure sum identity — from hg=0 and habove (g=0 on j≥1 chain entries),
-- the inr complement sum equals the negative of the inl chain-bottom sum.
-- Uses Fintype.sum_sigma + Fintype.sum_sum_type to split the sigma index, then
-- inr_simp (Fin 1 fiber) and inl_simp (habove kills j≥1, hv_chain supplies j=0).
-- entry_kind: Builder
theorem sum_bookkeeping_abstract
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W]
    (p m : ℕ) (l : Fin p → ℕ)
    (D : (Σ t : Fin p, Fin (l t)) → W)
    (CB : Fin m → W)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (hv_chain : ∀ (t : {t : Fin p // 0 < l t}) (i : Fin (l t.1)),
        v ⟨Sum.inl t, i.castSucc⟩ = D ⟨t.1, i⟩)
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = CB c)
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • CB c)
      = -(∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • D ⟨t.1, ⟨0, t.2⟩⟩) := by
  rw [eq_neg_iff_add_eq_zero, add_comm]
  rw [Fintype.sum_sigma, Fintype.sum_sum_type] at hg
  have inr_simp : ∀ c : Fin m,
      ∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
            (fun _ : Fin m => 1) (Sum.inr c)), g ⟨Sum.inr c, j⟩ • v ⟨Sum.inr c, j⟩
      = g ⟨Sum.inr c, (0 : Fin 1)⟩ • CB c := by
    intro c; simp [hv_C]
  simp_rw [inr_simp] at hg
  have inl_simp : ∀ t : {t : Fin p // 0 < l t},
      ∑ j : Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
            (fun _ : Fin m => 1) (Sum.inl t)), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩
      = g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • D ⟨t.1, ⟨0, t.2⟩⟩ := by
    intro t
    change ∑ j : Fin (l t.1 + 1), g ⟨Sum.inl t, j⟩ • v ⟨Sum.inl t, j⟩ = _
    rw [Fin.sum_univ_succ, add_comm]
    have hzero : ∑ i : Fin (l t.1), g ⟨Sum.inl t, i.succ⟩ • v ⟨Sum.inl t, i.succ⟩ = 0 := by
      apply Finset.sum_eq_zero
      intro i _
      simp [habove t i.succ (Fin.succ_pos i)]
    rw [hzero, zero_add]
    congr 1
    simpa [Fin.ext_iff] using hv_chain t ⟨0, t.2⟩
  simp_rw [inl_simp] at hg
  exact hg

-- entry_kind: Builder
-- chain_bottoms_mem_range_2: Submodule.coe_mem on basis elements closes the goal
-- d ⟨t,0⟩ : ↥N.range, so ↑(d ⟨t,0⟩) ∈ N.range; closed under smul + finite sum.
theorem chain_bottoms_mem_range_2
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
      ∈ LinearMap.range N := by
  apply Submodule.sum_mem
  intro t _
  apply Submodule.smul_mem
  exact (d ⟨↑t, ⟨0, t.2⟩⟩).2

-- Decompose into one strictly-more-abstract sub-goal: the pure sum-bookkeeping
-- identity, generic in `D`/`CB` (no `N`, no `LinearMap.range`, no `hd`).
-- Instantiate with `D := ↑(d ·)`, `CB := ↑(cb ·)` to recover the parent shape.
theorem comp_block_eq_neg_chain_bottoms_2
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W))
      = -(∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))  := by
  exact sum_bookkeeping_abstract p m l (fun s => (↑(d s) : W)) (fun c => (↑(cb c) : W))
    v hv_chain hv_C g hg habove

-- Direct leaf proof: complement coeffs vanish from `hmem` + disjointness + cb's LI.
-- The block `∑ c, g⟨inr c,0⟩ • cb c` lies in C (each cb c ∈ C); `hmem` puts it in `range N`;
-- `hC2`-disjointness collapses C ⊓ range N to ⊥, so the block = 0; then `cb.linearIndependent`
-- (pushed along the injective subtype) + `Fintype.linearIndependent_iff` kills every coeff.
theorem comp_coeffs_of_mem_range
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0)
    (hmem : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ LinearMap.range N) :
    ∀ (c : Fin m), g ⟨Sum.inr c, (0 : Fin 1)⟩ = 0  := by
  have hmemC : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ C :=
    Submodule.sum_mem C (fun c _ => Submodule.smul_mem C _ (cb c).2)
  have hmem2 : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ C ⊓ LinearMap.range N :=
    Submodule.mem_inf.mpr ⟨hmemC, hmem⟩
  have hbot : C ⊓ LinearMap.range N = ⊥ :=
    le_antisymm (disjoint_iff_inf_le.mp hC2) bot_le
  rw [hbot] at hmem2
  have hblock : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) = 0 :=
    (Submodule.mem_bot K).mp hmem2
  have hli : LinearIndependent K (fun c : Fin m => (cb c : W)) :=
    (cb.linearIndependent).map' (C.subtype) (LinearMap.ker_eq_bot.mpr Subtype.val_injective)
  intro c
  exact (Fintype.linearIndependent_iff.mp hli
    (fun c => g ⟨Sum.inr c, (0 : Fin 1)⟩) hblock) c

-- The complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`, via two sub-goals.
--   * `comp_block_eq_neg_chain_bottoms_2` : pure sum bookkeeping using `hg`, `habove`,
--     `hv_chain`, `hv_C` to rewrite the block as `-(∑ t, g⟨inl t,0⟩ • d⟨t.1,0⟩)`.
--     Strictly simpler: no `range N` reasoning, no linear independence.
--   * `chain_bottoms_mem_range_2` : the chain-bottom sum lies in `range N` since each
--     `↑(d ·) ∈ range N` and `range N` is closed under scalar mul + finite sum.
--     Strictly simpler: pure submodule closure facts, no full sum identity.
-- Combinator: rewrite via the equality, then `neg_mem` on the membership.
theorem comp_combo_mem_range
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W)) ∈ LinearMap.range N  := by
  have h_eq : (∑ c : Fin m, g ⟨Sum.inr c, (0 : Fin 1)⟩ • (cb c : W))
      = -(∑ t : {t : Fin p // 0 < l t},
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W)) :=
    comp_block_eq_neg_chain_bottoms_2
      N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove
  have h_mem : (∑ t : {t : Fin p // 0 < l t},
        g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))
      ∈ LinearMap.range N :=
    chain_bottoms_mem_range_2
      N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
      hv_chain hv_top hv_C g hg habove
  rw [h_eq]
  exact neg_mem h_mem

-- Complement coeffs `g ⟨inr c, 0⟩` vanish, given `habove` (above-bottom chain coeffs are 0).
-- Two simpler phases; the combinator just threads phase 1 into phase 2.
--   * `comp_combo_mem_range` : the complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`.
--     From `hg`, `habove` kills the above-bottom terms, leaving chain bottoms
--     (`v⟨inl t,0⟩ = d⟨t.1,0⟩ ∈ range N`) plus this block, so the block = minus that sum.
--     Strictly simpler: pure sum bookkeeping, no linear independence.
--   * `comp_coeffs_of_mem_range` : given that membership, the block is also in `C`
--     (each `cb c ∈ C`), so `hC2`-disjointness makes it 0 and `cb`-LI kills every coeff.
--     Strictly simpler: takes the membership as a hypothesis; only disjointness + LI remain.
theorem complement_coeffs
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    ∀ (c : Fin m), g ⟨Sum.inr c, (0 : Fin 1)⟩ = 0  := by
  have hmem := comp_combo_mem_range N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove
  exact comp_coeffs_of_mem_range N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove hmem

-- Given `habove` (all above-bottom coeffs vanish), every coeff vanishes by casing on `idx`.
--   * `chain_bottom_coeffs` : chain-bottom coeffs `g ⟨inl t, 0⟩` vanish (residual ∈ range N,
--     hC2-disjoint from C, then `chain_bottoms_li`). Strictly simpler: only the `j = 0` chain part.
--   * `complement_coeffs` : complement coeffs `g ⟨inr c, 0⟩` vanish (residual ∈ C, hC2-disjoint
--     from range N, then `cb`-LI). Strictly simpler: only the complement part.
-- Combinator is pure structural casing: above-bottom → `habove`, chain bottom → h_bottom,
-- complement (Fin 1, forced 0) → h_comp.
theorem bottom_complement_coeffs
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
    (hv_C : ∀ (c : Fin m), v ⟨Sum.inr c, (0 : Fin 1)⟩ = (cb c : W))
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K)
    (hg : ∑ i, g i • v i = 0)
    (habove : ∀ (t : {t : Fin p // 0 < l t}) (j : Fin (l t.1 + 1)), 0 < (j : ℕ) →
      g ⟨Sum.inl t, j⟩ = 0) :
    ∀ idx, g idx = 0  := by
  have h_bottom := chain_bottom_coeffs N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove
  have h_comp := complement_coeffs N hN h_inv p l d hd x hx C hC1 hC2 hC3 m cb v
    hv_chain hv_top hv_C g hg habove
  rintro ⟨s, j⟩
  cases s with
  | inl t =>
    rcases Nat.eq_zero_or_pos (j : ℕ) with hj | hj
    · have hj0 : j = (0 : Fin (l t.1 + 1)) := Fin.ext hj
      subst hj0; exact h_bottom t
    · exact habove t j hj
  | inr c =>
    have hj0 : j = (0 : Fin 1) := Fin.fin_one_eq_zero j
    subst hj0; exact h_comp c

end Library.LinearAlgebra.JordanForm.FamilyCoeffs
