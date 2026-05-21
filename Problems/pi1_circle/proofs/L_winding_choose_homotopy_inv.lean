import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs.L_lift_endpoint_mem_two_pi_int
import Problems.pi1_circle.proofs.L_lift_endpoint_eq_of_homotopic
import Problems.pi1_circle.proofs.L_int_mul_two_pi_inj

namespace Problems.pi1_circle

open Real

-- winding_choose_homotopy_inv: Classical.choose of lift_endpoint_mem_two_pi_int
-- is homotopy-invariant; follows from lift_endpoint_eq_of_homotopic plus
-- int_mul_two_pi_inj (the integer n with Γ(1)=n·2π is unique).
theorem winding_choose_homotopy_inv :
    ∀ (γ γ' : Path (1 : Circle) 1), Path.Homotopic γ γ' →
      Classical.choose (lift_endpoint_mem_two_pi_int γ)
        = Classical.choose (lift_endpoint_mem_two_pi_int γ') := by
  intro γ γ' h
  have heq := lift_endpoint_eq_of_homotopic γ γ' h
  have hm := Classical.choose_spec (lift_endpoint_mem_two_pi_int γ)
  have hn := Classical.choose_spec (lift_endpoint_mem_two_pi_int γ')
  apply int_mul_two_pi_inj
  linarith

end Problems.pi1_circle

