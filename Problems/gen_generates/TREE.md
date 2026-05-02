# gen_generates — TREE

_Auto-updated by dispatcher on every cascade._

```
main  (attempting, attempts=1)
├── via s124  (dead)
└── via s126  (proposed)
    ├── s126_sub_1  (attempting)
    │   └── via s127  (proposed)
    │       ├── s127_sub_1  (proved)
    │       └── s127_sub_2  (open, attempts=3)
    ├── s126_sub_2  (proved)
    │   └── via s130  (succeeded)
    │       ├── s130_sub_1  (proved, attempts=2)
    │       └── s130_sub_2  (proved)
    ├── s126_sub_3  (proved)
    │   └── via s128  (succeeded)
    │       ├── s128_sub_1  (proved)
    │       └── s128_sub_2  (proved)
    └── s126_sub_4  (proved)
        └── via s129  (succeeded)
            ├── s129_sub_1  (proved)
            └── s129_sub_2  (proved)
```

**Counters:** 10 proved / 2 attempting / 1 open
