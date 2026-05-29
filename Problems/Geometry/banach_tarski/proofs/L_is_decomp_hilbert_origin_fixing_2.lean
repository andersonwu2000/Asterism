import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs.L_is_decomp_hilbert_origin_fixing

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
theorem is_decomp_hilbert_origin_fixing_2 (A T : Set E) (ρ : E ≃ᵢ E) (f : E → E)
    (hf : ∀ x, x ∈ T → f x = ρ x) (hf' : ∀ x, x ∉ T → f x = x) (hρ0 : ρ 0 = 0) :
    ∃ S : Finset (E ≃ᵢ E), Equidecomp.IsDecompOn f A S ∧ ∀ s ∈ S, s 0 = 0 := by apply is_decomp_hilbert_origin_fixing <;> assumption

end Problems.Geometry.banach_tarski
