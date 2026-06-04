-- Two-step SOS bridge for the squared IMO 2006 polynomial inequality.
-- (A) `54·D² ≤ ((a-b)²+(b-c)²+(a-c)²)³` (D = (a-b)(b-c)(a-c)) — pure SOS
--     identity: RHS − LHS = 2·((a-2b+c)(2a-b-c)(a+b-2c))² ≥ 0.
-- (B) `256·u³·v ≤ 27·(u+v)⁴` for all reals u,v — pure SOS identity
--     RHS − LHS = (u−3v)²·(27u²+14uv+3v²) with both factors SOS.
-- Combine with u = ((a-b)²+(b-c)²+(a-c)²) = 3(a²+b²+c²)−(a+b+c)², v = (a+b+c)²:
-- ×v on A: 54·D²·v ≤ u³·v; ×256 then chain B: 13824·D²·v ≤ 27·(u+v)⁴.
-- Since u+v = 3(a²+b²+c²), RHS = 2187·(a²+b²+c²)⁴; divide by 27.
import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs
import Problems.Minif2f.imo_2006_p3.proofs._strategy_s9617

namespace Problems.Minif2f.imo_2006_p3

def bound_factored_form_squared := @Problems.Minif2f.imo_2006_p3.s9617

end Problems.Minif2f.imo_2006_p3
