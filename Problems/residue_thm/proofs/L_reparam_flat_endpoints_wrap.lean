-- Single-step alias: this goal has the exact signature of the proved sibling
-- `c1_path_smooth_reparam_flat_endpoints` (s10579). Per the wrapper-import
-- lesson, citing a proved sibling directly from `_strategy_*.lean` fails the
-- auto-import — route through a Builder sub-goal whose `L_*.lean` will
-- inherit the proved-sibling import for free.
import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10674

namespace Problems.residue_thm

def reparam_flat_endpoints_wrap := @Problems.residue_thm.s10674

end Problems.residue_thm
