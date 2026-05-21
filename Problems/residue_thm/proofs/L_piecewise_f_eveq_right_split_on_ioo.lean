-- Reduce eventually-equal-on-nhds to pointwise equality on the open neighborhood Ioo (1/2) 1.
-- Sub-goal piecewise_split_eq_pointwise_on_ioo provides the pointwise equality on Ioo (1/2) 1;
-- isOpen_Ioo.mem_nhds ht supplies Ioo (1/2) 1 ∈ nhds t, closing via Filter.eventuallyEq_of_mem.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10682

namespace Problems.residue_thm

def piecewise_f_eveq_right_split_on_ioo := @Problems.residue_thm.s10682

end Problems.residue_thm
