# pi1_circle — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s10688  (succeeded)
   └─ pi1_circle_bij_mulhom_to_int  (proved)
      └─ via s10689  (succeeded)
         └─ winding_int_iso_data  (proved)
            └─ via s10690  (succeeded)
               └─ winding_quotient_data  (proved)
                  └─ via s10691  (succeeded)
                     ├─ winding_quot_bijective  (proved)
                     │  └─ via s10693  (succeeded)
                     │     ├─ winding_quot_injective  (proved)
                     │     │  └─ via s10695  (succeeded)
                     │     │     └─ lift_endpoint_eq_imp_quot_eq  (proved)
                     │     │        └─ via s10697  (succeeded)
                     │     │           └─ paths_homotopic_from_lift_endpoint_eq  (proved, attempts=1)
                     │     │              └─ via s10700  (succeeded)
                     │     │                 └─ lifts_homotopic_rel_of_endpoint_eq  (proved)
                     │     │                    └─ via s10701  (succeeded)
                     │     │                       └─ real_paths_homotopic_rel_of_endpoints_eq  (proved)
                     │     │                          └─ via s10703  (succeeded)
                     │     └─ winding_quot_surjective  (proved)
                     │        └─ via s10696  (succeeded)
                     │           └─ exists_loop_lift_endpoint  (proved)
                     │              └─ via s10698  (succeeded)
                     │                 └─ standard_loop_data  (proved)
                     ├─ winding_quot_function_char  (proved, attempts=1)
                     │  └─ via s10692  (succeeded)
                     │     └─ winding_choose_homotopy_inv  (proved)
                     ├─ winding_quot_refl_zero  (proved)
                     └─ winding_quot_trans_add  (proved, attempts=1)
                        └─ via s10694  (succeeded)
                           └─ lift_endpoint_trans_eq_add  (proved)
                              └─ via s10699  (succeeded)
                                 ├─ lift_translation_eq_add  (proved)
                                 │  └─ via s10702  (succeeded)
                                 │     └─ lift_translation_proj_eq_loop  (proved)
                                 └─ lift_trans_endpoint  (proved)
```

## Forward

```
lift_endpoint_mem_two_pi_int  (proved)
└─ via s10687  (succeeded)

lift_endpoint_eq_of_homotopic  (proved)

int_mul_two_pi_inj  (proved)
```

**Counters:** 24 proved
