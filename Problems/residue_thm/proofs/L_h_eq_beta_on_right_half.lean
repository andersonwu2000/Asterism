-- Split ∫₀..t = ∫₀..(1/2) + ∫(1/2)..t at the midpoint; evaluate each half via FTC;
-- the left half collapses to α'(1) - α'(0), the right half to β'(2t-1) - β'(0);
-- the constant α'(0) + (α'(1) - α'(0)) cancels via h_match : α'(1) = β'(0).
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10676

namespace Problems.residue_thm

def h_eq_beta_on_right_half := @Problems.residue_thm.s10676

end Problems.residue_thm
