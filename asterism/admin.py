"""python -m asterism.admin --data DIR create-project --slug S --name NAME --repo URL --owner GITHUB_LOGIN
python -m asterism.admin --data DIR list-projects"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config, projects, util
from .store import Store


def main() -> int:
    ap = argparse.ArgumentParser(description="Asterism administration")
    ap.add_argument("--data", required=True, type=Path)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-project", help="create a project; the GitHub login becomes its owner on first sign-in")
    c.add_argument("--slug", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--repo", required=True)
    c.add_argument("--owner", required=True, help="the owner's GitHub login")
    sub.add_parser("list-projects")
    args = ap.parse_args()
    args.data.mkdir(parents=True, exist_ok=True)
    # Admin commands need no public URL or GitHub app; test mode settings let config.load succeed without them.
    config.use(config.load(args.data, port=0, test_mode=True))
    util.set_log(args.data.resolve() / "log.jsonl")
    store = Store(args.data.resolve())
    try:
        if args.cmd == "create-project":
            try:
                projects.create_project(store, args.slug, args.name, args.repo, args.owner)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
            util.log("project_created", project=args.slug, owner_login=args.owner)
            print(f"created project {args.slug}; {args.owner} becomes its owner on first sign-in")
        else:
            for slug in store.slugs():
                pj = projects.open_project(store, slug)
                r = pj.row()
                print(f"{slug}\t{r['name']}\t{r['repo']}\towner login: {r['owner_login']}")
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
