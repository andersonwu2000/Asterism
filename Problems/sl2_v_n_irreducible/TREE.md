# sl2_v_n_irreducible — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└── via s9906  (succeeded)
    └── v_mem_of_w_nonzero  (proved)
        └── via s9907  (succeeded)
            ├── exists_nonzero_scalar_v_in_w  (proved)
            │   └── via s9908  (succeeded)
            │       ├── descent_to_scalar_v  (proved)
            │       │   └── via s9909  (succeeded)
            │       │       ├── descent_witness  (proved)
            │       │       │   └── via s9910  (succeeded)
            │       │       │       ├── fpow_submodule_span_descent  (proved)
            │       │       │       │   └── via s9912  (succeeded)
            │       │       │       │       ├── e_pow_top_truncated_sum  (proved)
            │       │       │       │       │   └── via s9914  (succeeded)
            │       │       │       │       │       ├── e_pow_kills_lower_fpow_v  (proved)
            │       │       │       │       │       └── e_pow_m_fpow_m_eq_scalar_v  (proved)
            │       │       │       │       │           └── via s9916  (succeeded)
            │       │       │       │       │               ├── descfact_ne_zero  (proved)
            │       │       │       │       │               └── e_pow_fpow_eq_descfact_v  (proved)
            │       │       │       │       │                   └── via s9918  (succeeded)
            │       │       │       │       └── max_index_extraction  (proved, attempts=1)
            │       │       │       └── w_in_fpow_submodule_span  (proved)
            │       │       │           └── via s9911  (succeeded)
            │       │       │               └── lie_span_v_le_fpow_span  (proved)
            │       │       │                   └── via s9913  (succeeded)
            │       │       │                       └── fpow_span_lie_closed  (proved)
            │       │       │                           └── via s9915  (succeeded)
            │       │       │                               └── lie_y_fpow_v_mem  (proved)
            │       │       │                                   └── via s9917  (succeeded)
            │       │       │                                       ├── lie_e_fpow_v_mem  (proved)
            │       │       │                                       ├── lie_f_fpow_v_mem  (proved)
            │       │       │                                       └── lie_h_fpow_v_mem  (proved)
            │       │       └── iterate_e_in_w  (proved)
            │       └── nonzero_of_ne_bot  (proved)
            └── v_of_scalar_v_mem  (proved)
```

**Counters:** 22 proved
