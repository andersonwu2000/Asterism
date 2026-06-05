import Mathlib
import Problems.LinearAlgebra.courant_fischer.Defs

namespace Problems.LinearAlgebra.courant_fischer

-- orthobasis_repr_vanish_outside_span: repr coefficient vanishes at index i
-- when x lies in the span of the sub-family indexed by P and ¬P i holds,
-- because b i is orthogonal to every generator and hence to the whole span.
theorem orthobasis_repr_vanish_outside_span
    {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
    {n : ℕ} (b : OrthonormalBasis (Fin n) ℝ E)
    (P : Fin n → Prop)
    (x : E) (hx : x ∈ Submodule.span ℝ (b '' {j : Fin n | P j}))
    (i : Fin n) (hi : ¬ P i) :
    b.repr x i = 0 := by
  simp only [OrthonormalBasis.repr_apply_apply]
  apply Submodule.inner_left_of_mem_orthogonal hx
  rw [Submodule.mem_orthogonal']
  intro u hu
  refine Submodule.span_induction (p := fun u _ => inner ℝ (b i) u = (0 : ℝ)) ?_ ?_ ?_ ?_ hu
  · rintro s ⟨j, hPj, rfl⟩
    exact b.orthonormal.inner_eq_zero (fun h => hi (h ▸ hPj))
  · simp
  · intro v w _ _ hv hw
    rw [inner_add_right, hv, hw, add_zero]
  · intro r v _ hv
    rw [inner_smul_right, hv, mul_zero]



end Problems.LinearAlgebra.courant_fischer
