-- Vieta's: split into sum (a+b=7/2) and product (a*b=1) of roots.
-- Closer derives a≠1, b≠1 from Vieta (else b would have to equal both 5/2 and 1),
-- then field_simp + linarith reduces 1/(a-1)+1/(b-1)=-1 to a linear identity in a+b, ab.
import Mathlib
import Problems.Minif2f.mathd_algebra_131.Defs
import Problems.Minif2f.mathd_algebra_131.proofs._strategy_s9299

namespace Problems.Minif2f.mathd_algebra_131

def main := @Problems.Minif2f.mathd_algebra_131.s9299

end Problems.Minif2f.mathd_algebra_131
