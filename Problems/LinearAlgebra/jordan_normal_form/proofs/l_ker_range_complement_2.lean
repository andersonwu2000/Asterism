import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs

namespace Problems.LinearAlgebra.jordan_normal_form

-- ker_range_complement_2: Submodule.exists_isCompl (field → complementedLattice) finds C ≤ ker N
-- disjoint from range N, supplementing range N ⊓ ker N to all of ker N.
-- entry_kind: Builder
theorem ker_range_complement_2
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
  -- Find a complement of (range N ⊓ ker N) inside ker N (possible over a field).
  let S := (LinearMap.range N ⊓ LinearMap.ker N).comap (LinearMap.ker N).subtype
  obtain ⟨C₀, hC₀⟩ := Submodule.exists_isCompl S
  refine ⟨C₀.map (LinearMap.ker N).subtype, ?_, ?_, ?_⟩
  · -- C ≤ ker N: every image under ker N inclusion lies in ker N
    rintro x ⟨y, -, rfl⟩
    exact SetLike.coe_mem y
  · -- Disjoint C (range N)
    rw [Submodule.disjoint_def]
    intro x hxC hxR
    have hxKer : x ∈ LinearMap.ker N := by
      obtain ⟨y, -, rfl⟩ := hxC; exact SetLike.coe_mem y
    obtain ⟨y, hyC₀, rfl⟩ := hxC
    have hyS : y ∈ S := Submodule.mem_comap.mpr (Submodule.mem_inf.mpr ⟨hxR, hxKer⟩)
    have hbot : y ∈ S ⊓ C₀ := Submodule.mem_inf.mpr ⟨hyS, hyC₀⟩
    have hy0 : y = 0 := by
      have h : S ⊓ C₀ = ⊥ := hC₀.disjoint.eq_bot
      simp only [h, Submodule.mem_bot] at hbot; exact hbot
    simp [hy0]
  · -- C ⊔ (range N ⊓ ker N) = ker N
    ext x
    simp only [Submodule.mem_sup, Submodule.mem_map, Submodule.mem_inf]
    constructor
    · rintro ⟨a, ⟨ya, -, rfl⟩, b, ⟨-, hbK⟩, rfl⟩
      exact (LinearMap.ker N).add_mem (SetLike.coe_mem ya) hbK
    · intro hxK
      let x' : ↥(LinearMap.ker N) := ⟨x, hxK⟩
      have hx'top : x' ∈ S ⊔ C₀ := hC₀.sup_eq_top ▸ Submodule.mem_top
      obtain ⟨s, hs, c, hc, hsc⟩ := Submodule.mem_sup.mp hx'top
      have hs_inf : (s : W) ∈ LinearMap.range N ⊓ LinearMap.ker N :=
        Submodule.mem_comap.mp hs
      have heq : (s : W) + (c : W) = x := by
        have h : ((s + c : ↥(LinearMap.ker N)) : W) = x := congr_arg Subtype.val hsc
        simpa using h
      exact ⟨c.1, ⟨c, hc, rfl⟩, s.1, hs_inf, (add_comm (c : W) (s : W)).trans heq⟩

end Problems.LinearAlgebra.jordan_normal_form