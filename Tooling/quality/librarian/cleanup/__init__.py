"""Per-file Library cleanup stages, extracted from `dedup.py`.

`_common` holds the shared low-level helpers (imports nothing from
`dedup.py`); each stage module calls through `_common`. This package
re-exports only the six stage entry functions.
"""
from .audit import file_cleanup_audit
from .decide import file_cleanup_decide
from .mechanical import (file_cleanup_strip_framework_comments,
                         file_cleanup_unused_args)
from .polish import file_cleanup_polish
from .simplify import decl_cleanup_simplify_file

__all__ = [
    "decl_cleanup_simplify_file",
    "file_cleanup_audit",
    "file_cleanup_decide",
    "file_cleanup_polish",
    "file_cleanup_strip_framework_comments",
    "file_cleanup_unused_args",
]
