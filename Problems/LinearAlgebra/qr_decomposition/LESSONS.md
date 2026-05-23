<!-- Lessons learned across spawns on this problem.
     One sentence per `- ` bullet. Reflection spawn appends
     below this header; the divider line below is the
     anchor Edit tool relies on. -->

<!-- LESSONS_BEGIN -->
- Use `induction hx using Submodule.span_induction with | mem y hy => ... | zero => ... | add a b _ _ iha ihb => ... | smul c a _ iha => ...` for span membership induction; both positional and `(p := ...)` named-arg styles fail to elaborate. `Submodule.mem_orthogonal` yields `∀ y ∈ K, inner ℝ y x = 0` (y-first), so use `real_inner_comm` to flip to `inner ℝ x y = 0`.
- Mathlib's Gram-Schmidt API lives under the `InnerProductSpace` namespace (NOT root): use `InnerProductSpace.gramSchmidtNormed ℝ v`, `InnerProductSpace.gramSchmidtNormed_orthonormal hv : Orthonormal ℝ _`, and chain `InnerProductSpace.span_gramSchmidtNormed v s` (normed↔plain span equality, `v` and `s` are explicit, 𝕜 implicit) with `InnerProductSpace.span_gramSchmidt_Iic ℝ v i` (`span (gramSchmidt '' Iic i) = span (v '' Iic i)`) to reduce `v i ∈ span (gramSchmidtNormed ℝ v '' Iic i)` to `Submodule.subset_span ⟨i, Set.self_mem_Iic, rfl⟩`.
- To transport `LinearIndependent ℝ f` through a `LinearEquiv e`, rewrite `f = e ∘ g` by `rfl` then use `hli.map' e.toLinearMap (LinearEquiv.ker _)`; `LinearEquiv.ker _` closes the `ker = ⊥` obligation without any extra injectivity argument.
- `EuclideanSpace.inner_apply` does not exist; use `PiLp.inner_apply` to expand `inner ℝ (v : EuclideanSpace ℝ ι) w` into `∑ i, inner ℝ (v.ofLp i) (w.ofLp i)`, then close the scalar `inner ℝ (a : ℝ) b = a * b` sub-goal with `simp [Inner.inner, mul_comm]`.
- `Matrix.mulVec_single` (simp lemma) gives `A.mulVec (Pi.single i 1) = A.transpose i`, making it the standard bridge to express columns of `A` as images of `A.mulVecLin`; `Matrix.nonsing_inv_mul A h` requires `h : IsUnit A.det` (not `A.det ≠ 0`), so pass `isUnit_iff_ne_zero.mpr hdet`.
- `A.transpose i : Fin n → ℝ` is NOT elaboration-defeq to `EuclideanSpace ℝ (Fin n)`; bridge with `(EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose i)` (or `WithLp.equiv 2 _`) when feeding columns to `Orthonormal` / `gramSchmidt` / `Submodule.span` in the inner-product setting.
