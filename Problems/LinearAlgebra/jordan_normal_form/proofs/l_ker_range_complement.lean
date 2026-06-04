import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- ker_range_complement: complement of (range N ⊓ ker N) inside ker N via
-- Submodule.exists_isCompl on the comap into ker N, giving C ≤ ker N,
-- Disjoint C (range N), and C ⊔ (range N ⊓ ker N) = ker N.
-- entry_kind: Builder
theorem ker_range_complement
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        (N.restrict h_inv) (d ⟨t, j⟩) = 0 ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩) :
    ∃ C : Submodule K W,
      C ≤ LinearMap.ker N ∧ Disjoint C (LinearMap.range N) ∧
        C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N := by
  let P : Submodule K (LinearMap.ker N) :=
    (LinearMap.range N ⊓ LinearMap.ker N).comap (LinearMap.ker N).subtype
  obtain ⟨Q, hQ⟩ := Submodule.exists_isCompl P
  refine ⟨Q.map (LinearMap.ker N).subtype, ?_, ?_, ?_⟩
  · rintro x ⟨y, -, rfl⟩; exact y.2
  · rw [Submodule.disjoint_def]
    rintro x ⟨y, hyQ, rfl⟩ hxR
    have hyP : y ∈ P := by
      simp only [P, Submodule.mem_comap, Submodule.mem_inf]
      exact ⟨hxR, y.2⟩
    have hyzero : y = 0 := by
      have hdisj := hQ.disjoint
      rw [Submodule.disjoint_def] at hdisj
      exact hdisj y hyP hyQ
    simp [hyzero]
  · ext x
    simp only [Submodule.mem_sup, Submodule.mem_map, Submodule.mem_inf]
    constructor
    · rintro ⟨c, ⟨y, hyQ, rfl⟩, r, ⟨hrR, hrK⟩, hsum⟩
      rw [← hsum]; exact Submodule.add_mem _ y.2 hrK
    · intro hxK
      let xK : LinearMap.ker N := ⟨x, hxK⟩
      have htop : P ⊔ Q = ⊤ := hQ.sup_eq_top
      have hxK_top : xK ∈ (⊤ : Submodule K (LinearMap.ker N)) := Submodule.mem_top
      rw [← htop] at hxK_top
      simp only [Submodule.mem_sup] at hxK_top
      obtain ⟨a, haP, b, hbQ, hab⟩ := hxK_top
      have haP' : a.val ∈ LinearMap.range N ∧ a.val ∈ LinearMap.ker N := by
        have := haP
        simp only [P, Submodule.mem_comap, Submodule.mem_inf] at this
        exact this
      have hval : a.val + b.val = x := by
        have := congr_arg Subtype.val hab
        simpa using this
      exact ⟨b.val, ⟨b, hbQ, rfl⟩, a.val, ⟨haP'.1, haP'.2⟩, by rw [add_comm]; exact hval⟩

end Problems.LinearAlgebra.jordan_normal_form
