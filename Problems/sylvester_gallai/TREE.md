# sylvester_gallai — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (proved)
└─ via s10205  (succeeded)
   ├─ kelly_min_implies_ordinary  (proved)
   │  └─ via s10207  (succeeded)
   │     └─ exists_smaller_triple  (proved, attempts=1)
   │        ├─ via s10209  (dead)
   │        └─ via s10213  (succeeded)
   │           └─ kelly_smaller_with_param  (proved, attempts=1)
   │              └─ via s10214  (succeeded)
   │                 └─ kelly_smaller_two_same_side  (proved)
   │                    └─ via s10215  (succeeded)
   │                       └─ kelly_smaller_two_same_side_ordered  (proved)
   │                          └─ via s10216  (succeeded)
   │                             ├─ b_ne_r_when_on_param_line  (proved)
   │                             ├─ not_collinear_b_r_a_param  (proved)
   │                             └─ perpdist_strict_smaller_for_closer_a  (proved)
   │                                └─ via s10217  (succeeded)
   │                                   ├─ det_sq_pos_of_not_collinear  (proved)
   │                                   ├─ newnum_sq_factors  (proved)
   │                                   ├─ qp_sq_sum_pos_of_ne  (proved)
   │                                   ├─ rb_sq_decomp  (proved)
   │                                   └─ tdiff_ba_le_bf_sq  (proved)
   └─ min_perp_dist_triple  (proved)
      └─ via s10206  (succeeded)
         ├─ min_perp_over_valid_triples  (proved)
         │  └─ via s10208  (succeeded)
         │     └─ min_arg_valid_triple  (proved)
         └─ valid_triple_exists  (proved)
```

## Forward

```
three_reals_same_side  (proved)
└─ via s10210  (succeeded)

collinear_iff_param  (proved)
└─ via s10211  (succeeded)
   ├─ collinear_of_param  (proved)
   └─ param_of_collinear  (proved)
      └─ via s10212  (succeeded)
         ├─ param_x_case  (proved)
         └─ param_y_case  (proved)

perp_numerator_sq_param_factor  (proved)
```

**Counters:** 25 proved
