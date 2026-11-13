"""python -m asterism.server --data DIR --port N [--test-mode]"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from . import config, util, web
from .store import Store


def main() -> None:
    ap = argparse.ArgumentParser(description="Asterism server")
    ap.add_argument("--data", required=True, type=Path, help="data directory: config.json, databases, log.jsonl")
    ap.add_argument("--port", required=True, type=int)
    ap.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1, behind a proxy)")
    ap.add_argument("--test-mode", action="store_true",
                    help="replace GitHub sign-in with POST /test/login; never use this on a reachable server")
    args = ap.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    s = config.use(config.load(args.data, args.port, args.test_mode))
    util.set_log(s.data / "log.jsonl")
    util.log("server_started", public_url=s.public_url, test_mode=s.test_mode)
    app = web.build_app(Store(s.data))
    # No access log: request paths carry invitation codes and user codes, which must not be written down.
    uvicorn.run(app, host=args.host, port=args.port, access_log=False, log_level="warning")


if __name__ == "__main__":
    main()
