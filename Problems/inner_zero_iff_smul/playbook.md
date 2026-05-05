- **Inner product zero iff equal-norm under scaling**: Split iff via identity `‖x+α•y‖²−‖x−α•y‖²=4α⟨x,y⟩` using `norm_add_sq_real`/`norm_sub_sq_real`+`inner_smul_right`+`ring`, then instantiate at α=1 for backward direction.

- **Inner product zero iff symmetric smul norms**: Reduce to algebraic identity `‖x+α•y‖²-‖x-α•y‖²=4α⟨x,y⟩` via `norm_add_sq_real`/`norm_sub_sq_real`, then split iff with `sq_left_inj`/`norm_nonneg` (fwd) and `α=1` instantiation (rev).
