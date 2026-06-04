-- Split the conjunction into the three Vieta identities for the monic cubic f.
-- (1) `vieta_sum`: a+b+c = -3 (coefficient of x²).
-- (2) `vieta_pair`: ab+bc+ca = 4 (coefficient of x).
-- (3) `vieta_prod`: abc = 11 (constant term, negated).
-- Each sub-goal is strictly simpler (one equation, not a 3-conjunction) and
-- shares the full parent hypothesis bundle; combinator is `⟨_,_,_⟩`.
import Mathlib
import Problems.Minif2f.aime_1996_p5.Defs
import Problems.Minif2f.aime_1996_p5.proofs._strategy_s9387

namespace Problems.Minif2f.aime_1996_p5

def vieta_f := @Problems.Minif2f.aime_1996_p5.s9387

end Problems.Minif2f.aime_1996_p5
