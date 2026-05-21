-- Decompose via the lifted endpoint Γ γ 1 ∈ 2π·ℤ: (1) build W' on the
-- homotopy quotient with characterizing equation Γ γ 1 = W'⟦γ⟧ * (2π);
-- (2-4) the three properties refl=0 / trans=add / bijective each follow
-- from that characterizing equation (W'⟦refl⟧=0 via `liftPath_const`,
-- additivity via `liftPath_trans` + translation invariance of lifts,
-- bijectivity via `monodromy_bijective` + standard loops `t ↦ exp(t·n·2π)`).
import Mathlib
import Problems.pi1_circle.Defs
import Problems.pi1_circle.proofs._strategy_s10691

namespace Problems.pi1_circle

def winding_quotient_data := @Problems.pi1_circle.s10691

end Problems.pi1_circle
