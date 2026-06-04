-- Adding μ•1 to a zero-diagonal Jordan matrix preserves Jordan form, via toMatrix linearity.
-- Sub-goals: (1) `to_matrix_add_smul_one` — toMatrix distributes the μ•1 shift;
-- (2) `jordan_add_const_diag` — adding c•1 to a zero-diagonal Jordan matrix stays Jordan.
-- Closer rewrites the toMatrix expression and applies the matrix-level shift fact.
import Mathlib
import Problems.LinearAlgebra.jordan_normal_form.Defs
import Problems.LinearAlgebra.jordan_normal_form.proofs._strategy_s11031

namespace Problems.LinearAlgebra.jordan_normal_form

def jordan_form_add_smul_one := @Problems.LinearAlgebra.jordan_normal_form.s11031

end Problems.LinearAlgebra.jordan_normal_form
