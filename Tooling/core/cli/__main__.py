"""`python -m Tooling.core.cli` entry point.

The pre-split `cli.py` doubled as both a library module and a runnable
script (`if __name__ == "__main__": sys.exit(main())` at its tail); the
package split (task A3, move-only) moved `main()` into `main.py`, whose
own module name is never `"__main__"` when imported normally. This file
is the package's `-m`-invocation surface, preserving the exact
`python -m Tooling.core.cli <args>` invocation used by
`daemon_start`/`dispatcher._spawn_handoff_successor`'s own relaunch
argv, `installer/systemd/asterism-daemon.service`, and
`installer/launch.ps1`."""
from __future__ import annotations

import sys

from . import main

if __name__ == "__main__":
    sys.exit(main())
