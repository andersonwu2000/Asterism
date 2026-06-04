import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_inf_ker_card

namespace Problems.LinearAlgebra.jordan_normal_form

-- finrank W via rank-nullity over N: split finrank W = finrank(range N) + finrank(ker N),
-- then count each piece. h_rn (mathlib rank-nullity), h_range = ∑ l (basis d card, inline),
-- h_ker = finrank(range⊓ker) + m (disjoint-sup count on hC2/hC3, inline). Only genuine
-- sub-goal: inf_ker_card = #{0<l t} (strong-hd count, the j=0 constraint forces proper
-- chains so ker(N↾range) = span of chain bottoms). omega assembles the four ℕ equalities.
theorem s10997
    {K W : Type*} [Field K] [AddCommGroup W] [Module K W] [FiniteDimensional K W]
    (N : W →ₗ[K] W) (hN : IsNilpotent N)
    (h_inv : ∀ x ∈ LinearMap.range N, N x ∈ LinearMap.range N)
    (p : ℕ) (l : Fin p → ℕ)
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K (LinearMap.range N))
    (hd : ∀ (t : Fin p) (j : Fin (l t)),
        ((j : ℕ) = 0 ∧ (N.restrict h_inv) (d ⟨t, j⟩) = 0) ∨
          ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧
            (N.restrict h_inv) (d ⟨t, j⟩) = d ⟨t, i⟩)
    (C : Submodule K W) (hC1 : C ≤ LinearMap.ker N)
    (hC2 : Disjoint C (LinearMap.range N))
    (hC3 : C ⊔ (LinearMap.range N ⊓ LinearMap.ker N) = LinearMap.ker N)
    (m : ℕ) (cb : Module.Basis (Fin m) K C) :
    Module.finrank K W = (∑ t : Fin p, l t) + Fintype.card {t : Fin p // 0 < l t} + m  := by
  have h_rn : Module.finrank K (LinearMap.range N) + Module.finrank K (LinearMap.ker N)
      = Module.finrank K W :=
    LinearMap.finrank_range_add_finrank_ker N
  have h_range : Module.finrank K (LinearMap.range N) = ∑ t : Fin p, l t := by
    rw [Module.finrank_eq_card_basis d, Fintype.card_sigma]
    simp [Fintype.card_fin]
  have h_ker : Module.finrank K (LinearMap.ker N)
      = Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W) + m := by
    have hdisjoint : Disjoint C (LinearMap.range N ⊓ LinearMap.ker N) :=
      hC2.mono_right inf_le_left
    have hsup := Submodule.finrank_sup_add_finrank_inf_eq C
      (LinearMap.range N ⊓ LinearMap.ker N)
    have hbot : (C ⊓ (LinearMap.range N ⊓ LinearMap.ker N) : Submodule K W) = ⊥ :=
      disjoint_iff.mp hdisjoint
    have hm : Module.finrank K C = m := by
      rw [Module.finrank_eq_card_basis cb, Fintype.card_fin]
    rw [hbot, hC3, finrank_bot K W] at hsup
    omega
  have h_inf : Module.finrank K (LinearMap.range N ⊓ LinearMap.ker N : Submodule K W)
      = Fintype.card {t : Fin p // 0 < l t} := inf_ker_card N hN h_inv p l d hd
  omega

end Problems.LinearAlgebra.jordan_normal_form
