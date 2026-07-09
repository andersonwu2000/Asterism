import Mathlib.Analysis.InnerProductSpace.Basic
import Mathlib.Analysis.Normed.Group.Basic
import Mathlib.Analysis.Normed.Operator.Basic
import Mathlib.Analysis.RCLike.Basic
import Mathlib.Topology.Algebra.Module.FiniteDimension

/-!
# Auxiliary lemmas for Eckart–Young

This file collects small auxiliary results used in the proof of the Eckart–Young theorem.
The main content is a pair of lemmas that lift a pointwise lower bound on $\|Ax\|$ to a lower
bound on the operator norm $\|A\|$.

## Main statements

- `opnorm_ge_of_vector_bound`: if $c \cdot \|x\| \le \|Ax\|$ for some nonzero vector $x$,
  then $c \le \|A\|$.
- `opnorm_ge_of_pointwise_bound`: alias of `opnorm_ge_of_vector_bound` with a renamed variable.
-/

namespace Library.LinearAlgebra.EckartYoung.Auxiliary

/-- If $c \cdot \|x\| \le \|Ax\|$ for some nonzero vector $x$, then $c \le \|A\|$.

This follows by combining `ContinuousLinearMap.le_opNorm` with a cancellation of $\|x\| > 0$. -/
theorem opnorm_ge_of_vector_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F]
    (A : E →ₗ[𝕜] F) (x : E) (c : ℝ)
    (hx : x ≠ 0) (hbound : c * ‖x‖ ≤ ‖A x‖) :
    c ≤ ‖A.toContinuousLinearMap‖ := by
  have hxpos : 0 < ‖x‖ := norm_pos_iff.mpr hx
  have hle : ‖A x‖ ≤ ‖A.toContinuousLinearMap‖ * ‖x‖ := by
    simpa using A.toContinuousLinearMap.le_opNorm x
  exact le_of_mul_le_mul_right (hbound.trans hle) hxpos

/-- Alias of `opnorm_ge_of_vector_bound` with variable renamed from `x` to `y`. -/
theorem opnorm_ge_of_pointwise_bound {𝕜 : Type*} [RCLike 𝕜]
    {E F : Type*} [NormedAddCommGroup E] [InnerProductSpace 𝕜 E] [FiniteDimensional 𝕜 E]
    [NormedAddCommGroup F] [InnerProductSpace 𝕜 F] [FiniteDimensional 𝕜 F]
    (A : E →ₗ[𝕜] F) (y : E) (c : ℝ) (hy : y ≠ 0) (h : c * ‖y‖ ≤ ‖A y‖) :
    c ≤ ‖A.toContinuousLinearMap‖ :=
  opnorm_ge_of_vector_bound A y c hy h

end Library.LinearAlgebra.EckartYoung.Auxiliary
