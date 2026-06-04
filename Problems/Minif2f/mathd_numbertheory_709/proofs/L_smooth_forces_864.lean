-- Split: extract 2^a·3^b factorization from {2,3} prime support, then solve τ-equations.
-- A. `exists_two_three_factorization` reduces the prime-support hypothesis to existence
--    of (a, b) with n = 2^a · 3^b — pure number-theory existence, no algebra.
-- B. `factorization_forces_864` does the algebra in (a, b): from τ(2·2^a·3^b)=(a+2)(b+1)=28
--    and τ(3·2^a·3^b)=(a+1)(b+2)=30 conclude a=5, b=3, so n = 2^5·3^3 = 864.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9700

namespace Problems.Minif2f.mathd_numbertheory_709

def smooth_forces_864 := @Problems.Minif2f.mathd_numbertheory_709.s9700

end Problems.Minif2f.mathd_numbertheory_709
