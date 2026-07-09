import Mathlib

/-!
# Jordan normal form — coefficient vanishing lemmas

This file establishes that every scalar coefficient in a hypothetical linear dependence among the
assembled Jordan-chain basis vectors must vanish. The argument proceeds in three layers: first
pushing `N` through the relation to extract a vanishing combination of range-basis elements
(`pushforward_d_relation`), then reading off the above-bottom coefficients by linear independence
(`above_bottom_vanish`), and finally killing the chain-bottom and complement coefficients by a
disjointness–linear-independence argument (`chain_bottom_coeffs`, `complement_coeffs`,
`bottom_complement_coeffs`).
-/

namespace Library.LinearAlgebra.JordanForm.FamilyCoeffs

variable {K W : Type*} [Field K] [AddCommGroup W] [Module K W]

/-- Given a vanishing linear combination `hrel` of coerced range-basis elements
`↑(d ⟨ti.1.1, ti.2⟩)`, forces every coefficient `g ⟨Sum.inl ti.1, ti.2.succ⟩` to zero
by linear independence of the injective subfamily of `d`. -/
theorem d_coeff_vanish
    [FiniteDimensional K W]
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

/-- For `j : Fin (l t.1 + 1)` with `0 < j`, the coefficient `g ⟨Sum.inl t, j⟩` vanishes:
translate the succ-form result of `d_coeff_vanish` via `j = (j.pred).succ`. -/
theorem li_extract_above
    [FiniteDimensional K W]
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

theorem n_distrib_smul_sum
    (N : W →ₗ[K] W)
    (p : ℕ) (l : Fin p → ℕ) (m : ℕ)
    (v : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → W)
    (g : (Σ s : ({t : Fin p // 0 < l t} ⊕ Fin m),
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1) (fun _ : Fin m => 1) s)) → K) :
    N (∑ i, g i • v i) = ∑ i, g i • N (v i) := by simp [map_sum, map_smul]

/-- Collapses `∑ g i • N (v i)` over all Jordan-family indices to the succ-indexed inl terms only:
inl-bottom terms vanish because the chain bottom maps to zero under `N` (by `hd`), and inr terms
vanish because `C ≤ ker N`. -/
theorem n_sum_collapse_to_inl_succ
    [FiniteDimensional K W]
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
          Fin (Sum.elim (fun t : {t : Fin p // 0 < l t} => l t.1 + 1)
               (fun _ : Fin m => 1) s)) → W)
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

/-- For each positive-length chain index `(t, j)`, applying `N` to the succ-step `v ⟨Sum.inl t, j.succ⟩`
yields the coerced `d`-basis element `↑(d ⟨t.1, j⟩)`, using the chain recurrence in `hd` and the
preimage relation `hx`. -/
theorem n_v_inl_succ_eq_d
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

/-- Computes `N (∑ g i • v i)` as the weighted sum `∑ g⟨inl ti.1, ti.2.succ⟩ • ↑(d ⟨ti.1.1, ti.2⟩)`
by combining linearity of `N`, collapse of vanishing terms, and the per-element chain shift. -/
theorem pushforward_d_eq_alias
    [FiniteDimensional K W]
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

/-- Derives the vanishing relation `∑ g⟨inl ti.1, ti.2.succ⟩ • ↑(d ⟨ti.1.1, ti.2⟩) = 0` from
`hg : ∑ g i • v i = 0` by applying `N` and using `pushforward_d_eq_alias`. -/
theorem pushforward_d_relation
    [FiniteDimensional K W]
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

/-- All above-bottom coefficients `g ⟨Sum.inl t, j⟩` with `0 < j` vanish: push `N` through
`hg` via `pushforward_d_relation` to obtain a vanishing combination in the range basis, then
apply `li_extract_above` to read off the coefficients by linear independence. -/
theorem above_bottom_vanish
    [FiniteDimensional K W]
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

/-- Given a vanishing weighted sum `hzero` of chain-bottom basis elements `↑(d ⟨t.1, 0⟩)`,
forces every chain-bottom coefficient `g ⟨Sum.inl t, 0⟩` to zero by linear independence of
the injective subfamily `t ↦ d ⟨t.1, ⟨0, t.2⟩⟩` of the range basis `d`. -/
theorem chain_bottom_coeffs_of_sum_zero
    [FiniteDimensional K W]
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

/-- Given `hres` expressing that the chain-bottom sum plus the complement sum equals zero,
the chain-bottom sum alone is zero because it lies in `range N` while the complement sum
lies in `C`, and `hC2`-disjointness forces `C ∩ range N = ⊥`. -/
theorem chain_bottom_range_part_zero
    [FiniteDimensional K W]
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

/-- After zeroing above-bottom coefficients via `habove`, the vanishing sum `hg` reduces to
`(∑_t g⟨inl t,0⟩ • ↑(d ⟨t.1,0⟩)) + (∑_c g⟨inr c,0⟩ • ↑(cb c)) = 0` by splitting over
the Σ/⊕ index and using `habove` to kill all `j ≥ 1` terms. -/
theorem chain_bottom_residual
    [FiniteDimensional K W]
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

/-- All chain-bottom coefficients `g ⟨Sum.inl t, 0⟩` vanish, given `habove`: thread the
residual sum through `chain_bottom_range_part_zero` to isolate the chain-bottom part in
`range N`, then apply `chain_bottom_coeffs_of_sum_zero` via linear independence. -/
theorem chain_bottom_coeffs
    [FiniteDimensional K W]
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

/-- Pure sum identity, abstract in `D` and `CB`: given `hg = 0` and `habove`, the complement
sum `∑ c, g⟨inr c,0⟩ • CB c` equals the negation of the chain-bottom sum
`∑ t, g⟨inl t,0⟩ • D ⟨t.1,0⟩`, using only the sigma-sum splitting and `habove` to kill
above-bottom terms without any module-structure hypotheses. -/
theorem sum_bookkeeping_abstract
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

/-- The weighted sum of chain-bottom coerced basis elements lies in `range N`, since each
`↑(d ⟨t, 0⟩)` belongs to `range N` and the submodule is closed under scalar multiplication
and finite sums. -/
theorem chain_bottoms_mem_range_2
    [FiniteDimensional K W]
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

/-- The complement block equals the negation of the chain-bottom sum, obtained by instantiating
`sum_bookkeeping_abstract` with `D := ↑(d ·)` and `CB := ↑(cb ·)`. -/
theorem comp_block_eq_neg_chain_bottoms_2
    [FiniteDimensional K W]
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
            g ⟨Sum.inl t, (0 : Fin (l t.1 + 1))⟩ • (↑(d ⟨t.1, ⟨0, t.2⟩⟩) : W))  := Library.LinearAlgebra.JordanForm.FamilyCoeffs.sum_bookkeeping_abstract p m l (fun s => (↑(d s) : W)) (fun c => (↑(cb c) : W)) v hv_chain hv_C g hg habove

/-- Given that the complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`, all complement
coefficients vanish: the block also lies in `C`, so `hC2`-disjointness forces it to zero, and
linear independence of `cb` (pushed along the injective subtype `C ↪ W`) finishes the argument. -/
theorem comp_coeffs_of_mem_range
    [FiniteDimensional K W]
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

/-- The complement block `∑ c, g⟨inr c,0⟩ • cb c` lies in `range N`: it equals the negation of
the chain-bottom sum (by `comp_block_eq_neg_chain_bottoms_2`), which itself lies in `range N`
(by `chain_bottoms_mem_range_2`), and `range N` is closed under negation. -/
theorem comp_combo_mem_range
    [FiniteDimensional K W]
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

/-- All complement coefficients `g ⟨Sum.inr c, 0⟩` vanish given `habove`: show the complement
block lies in `range N` via `comp_combo_mem_range`, then apply `comp_coeffs_of_mem_range`. -/
theorem complement_coeffs
    [FiniteDimensional K W]
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

/-- Every coefficient `g idx` vanishes given `habove` (all above-bottom chain coefficients are zero):
cases on `idx` to dispatch chain-bottom indices to `chain_bottom_coeffs` and complement indices
to `complement_coeffs`. -/
theorem bottom_complement_coeffs
    [FiniteDimensional K W]
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
