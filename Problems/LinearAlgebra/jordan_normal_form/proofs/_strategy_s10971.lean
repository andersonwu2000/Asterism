import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_coord_m_eq_coord
import Problems.LinearAlgebra.jordan_normal_form.proofs.L_repr_comp_linear

namespace Problems.LinearAlgebra.jordan_normal_form

-- ker M coords above the chain bottoms vanish: M is a down-shift on the basis d, so
-- coord of w at ⟨t,j⟩ (j≥1) = coord of M w at predecessor ⟨t,i⟩, = 0 since M w = 0.

-- (1) coord_m_eq_coord: per-basis-vector identity d.repr(M(d idx))⟨t,i⟩ = d.repr(d idx)⟨t,j⟩;
-- (2) repr_comp_linear: abstract lift of that identity from basis vectors to all w via Basis.ext.
theorem s10971
    {K R : Type*} [Field K] [AddCommGroup R] [Module K R] [FiniteDimensional K R]
    (M : R →ₗ[K] R) {p : ℕ} {l : Fin p → ℕ}
    (d : Module.Basis (Σ t : Fin p, Fin (l t)) K R)
    (hbot : ∀ (t : Fin p) (j : Fin (l t)), (j : ℕ) = 0 → M (d ⟨t, j⟩) = 0)
    (hshift : ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) →
      ∃ i : Fin (l t), (i : ℕ) + 1 = (j : ℕ) ∧ M (d ⟨t, j⟩) = d ⟨t, i⟩)
    (w : R) (hw : M w = 0) :
    ∀ (t : Fin p) (j : Fin (l t)), 0 < (j : ℕ) → d.repr w ⟨t, j⟩ = 0  := by
  intro t j hj
  obtain ⟨i, hij, hMij⟩ := hshift t j hj
  have hbasis := coord_m_eq_coord M d hbot hshift t j i hij hMij
  have htransfer := repr_comp_linear M d ⟨t, i⟩ ⟨t, j⟩ hbasis w
  rw [hw, map_zero, Finsupp.zero_apply] at htransfer
  exact htransfer.symm


end Problems.LinearAlgebra.jordan_normal_form
