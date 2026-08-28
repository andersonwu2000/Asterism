"""Package entry point. The daemon launches the gateway as
`python -m Tooling.lsp.gateway` (`lsp/lifecycle.start_gateway`), and a
package cannot be run that way without this file — the `if __name__ ==
"__main__": main()` tail of the former `gateway.py` moved here when the
module became a package (2026-08-29, split A1-1).
"""
from __future__ import annotations

from . import main

if __name__ == "__main__":
    main()
