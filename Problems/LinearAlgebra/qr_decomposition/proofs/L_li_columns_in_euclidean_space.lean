import Mathlib
import Problems.LinearAlgebra.qr_decomposition.Defs

namespace Problems.LinearAlgebra.qr_decomposition

-- li_columns_in_euclidean_space: transport LinearIndependent through LinearEquiv.symm
-- Uses LinearIndependent.map' with (EuclideanSpace.equiv).symm.toLinearMap and LinearEquiv.ker.
-- entry_kind: Builder

theorem li_columns_in_euclidean_space {n : ℕ}
    (A : Matrix (Fin n) (Fin n) ℝ) :
    LinearIndependent ℝ A.transpose →
    LinearIndependent ℝ
      (fun i : Fin n => (EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose i)) := by
  intro hli
  have heq : (fun i : Fin n => (EuclideanSpace.equiv (Fin n) ℝ).symm (A.transpose i)) =
      (EuclideanSpace.equiv (Fin n) ℝ).symm ∘ A.transpose := rfl
  rw [heq]
  exact hli.map' (EuclideanSpace.equiv (Fin n) ℝ).symm.toLinearMap (LinearEquiv.ker _)

end Problems.LinearAlgebra.qr_decomposition
