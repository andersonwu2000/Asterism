"""gateway.log carries no timestamps: two post-mortems on 2026-08-30
(the flagship's 12:23Z/12:45Z backend restarts, the local shed/rewarm
churn) had to be dated from `ps lstart` and could not be windowed at
all. Every line the gateway writes to stderr is stamped UTC."""
from __future__ import annotations

import io
import re

from Tooling.lsp.gateway.stamp import Timestamped

STAMP = r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ "


def test_every_line_is_stamped_once_even_across_partial_writes() -> None:
    buf = io.StringIO()
    w = Timestamped(buf)
    w.write("[gateway] a\n[gateway] b\n")
    w.write("[gateway] part")
    w.write("ial\n")
    lines = buf.getvalue().splitlines()
    assert len(lines) == 3, lines
    assert all(re.match(STAMP + r"\[gateway\] ", ln) for ln in lines), lines
    assert lines[2].endswith("[gateway] partial")
    w.flush()

