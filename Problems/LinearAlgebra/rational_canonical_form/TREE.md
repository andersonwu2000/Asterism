# LinearAlgebra.rational_canonical_form — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved, attempts=2)
└─ via s11591  (succeeded)
   └─ companion_block_basis  (proved)
      └─ via s11592  (succeeded)
         ├─ block_assembly  (proved)
         │  └─ via s11593  (succeeded)
         │     ├─ block_diag  (proved, attempts=1)
         │     │  ├─ via s11594  (dead)
         │     │  └─ via s11595  (succeeded)
         │     │     ├─ dfinsupp_basis_repr_component  (proved)
         │     │     ├─ lsmul_x_diag_component  (proved, attempts=2)
         │     │     │  ├─ via s11596  (dead)
         │     │     │  └─ via s11598  (succeeded)
         │     │     │     └─ dfinsupp_basis_diag_component  (proved)
         │     │     └─ lsmul_x_offdiag_repr_zero  (proved, attempts=2)
         │     │        └─ via s11599  (succeeded)
         │     │           └─ lsmul_x_offdiag_component_zero  (proved)
         │     │              └─ via s11600  (succeeded)
         │     │                 └─ dfinsupp_basis_offdiag_component_zero  (proved)
         │     ├─ conj_matrix  (proved)
         │     └─ intertwine_x  (proved)
         └─ block_companion  (proved)
```

## Forward

```
companion_matrix_eq_tomatrix_mulx  (proved)
└─ via s11589  (succeeded)
   ├─ modbymonic_coeff_eq_companion  (proved)
   │  └─ via s11590  (succeeded)
   │     ├─ xpow_modbymonic_lt  (proved)
   │     └─ xpow_modbymonic_self  (proved)
   └─ repr_mulleft_basis_eq_modbymonic  (proved)
```

**Counters:** 18 proved
