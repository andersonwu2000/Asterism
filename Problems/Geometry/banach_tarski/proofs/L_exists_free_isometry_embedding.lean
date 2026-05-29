-- Build φ as the LINEAR embedding ψ : F₂ →* (E ≃ₗᵢ[ℝ] E) post-composed with the
-- coercion homomorphism (·).toIsometryEquiv : (E ≃ₗᵢ[ℝ] E) →* (E ≃ᵢ E).
-- Sub-goal `free_so3_embedding` supplies ψ with: injectivity, and (per nontrivial word)
-- det = 1 and ψ w ≠ refl — the genuine SO(3) freeness/rotation content.
-- The remaining work is pure packaging: the coercion is an injective monoid hom
-- (so φ is injective), every ψ w is linear (so φ w fixes 0), and φ w x = x ⇔ ψ w x = x,
-- whence rotation_fixed_set_on_sphere_finite (proved sibling) gives the finite fixed set.
import Mathlib
import Problems.Geometry.banach_tarski.Defs
import Problems.Geometry.banach_tarski.proofs._strategy_s11470

namespace Problems.Geometry.banach_tarski

def exists_free_isometry_embedding := @Problems.Geometry.banach_tarski.s11470

end Problems.Geometry.banach_tarski
