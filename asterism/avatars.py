"""Avatars (1z): a member's picture in one project, like their name there. A person sets their own; an agent's is set
by its person. The page crops and scales the picture to 128x128 and sends a PNG or WebP; the server checks the bytes
by their header only (no image library) and keeps them in the project's database (the `avatars` table), served from
this origin to members with `read`. Members' views (people's, never agents') say which version each member has.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import sqlite3
import struct
from typing import Any

from . import projects, util
from .errors import bad_request, forbidden, not_found
from .projects import Actor, Project

SIDE = 128                  # pixels, both ways
MOST = 64 * 1024            # bytes of the picture
KINDS = ("person", "agent")
SHAPE = (f'Send {{"image": <base64 of a PNG or WebP of {SIDE}x{SIDE}, at most {MOST // 1024} KB>}}, '
         f'or {{"image": null}} to remove it.')


def _png_size(data: bytes) -> tuple[int, int] | None:
    # The signature, then the IHDR chunk first: length 13, its type, width and height (big-endian).
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[8:16] != b"\x00\x00\x00\x0dIHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _webp_size(data: bytes) -> tuple[int, int] | None:
    # RIFF with the length of what follows, WEBP, then the first chunk: VP8X (extended: the canvas), VP8L
    # (lossless) or VP8 (lossy), each with the size where its format puts it.
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    if struct.unpack("<I", data[4:8])[0] + 8 != len(data):
        return None
    kind = data[12:16]
    if kind == b"VP8X":
        w = int.from_bytes(data[24:27], "little") + 1
        h = int.from_bytes(data[27:30], "little") + 1
        return w, h
    if kind == b"VP8L":
        if data[20] != 0x2F:
            return None
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8 ":
        if data[23:26] != b"\x9d\x01\x2a":
            return None
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    return None


def check(image: Any) -> tuple[bytes, str]:
    """The bytes of a picture sent as base64, and its type; bad_request unless it is a PNG or WebP of SIDE x SIDE
    of at most MOST bytes."""
    if not isinstance(image, str) or len(image) > (MOST + 2) // 3 * 4 + 4:
        raise bad_request("bad_request", SHAPE)
    try:
        data = base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError):
        raise bad_request("bad_request", SHAPE) from None
    if len(data) > MOST:
        raise bad_request("bad_request", SHAPE)
    for size, mime in ((_png_size(data), "image/png"), (_webp_size(data), "image/webp")):
        if size is not None:
            if size != (SIDE, SIDE):
                raise bad_request("bad_request", f"The picture is {size[0]}x{size[1]}; it must be {SIDE}x{SIDE}.")
            return data, mime
    raise bad_request("bad_request", SHAPE)


def _store(pj: Project, kind: str, member_id: int, image: Any) -> dict[str, Any]:
    if image is None:
        with pj.db:
            pj.db.execute("DELETE FROM avatars WHERE member_kind = ? AND member_id = ?", (kind, member_id))
        return {"avatar": None}
    data, mime = check(image)
    version = hashlib.sha256(data).hexdigest()[:16]
    with pj.db:
        pj.db.execute("INSERT INTO avatars (member_kind, member_id, image, mime, version, at) VALUES (?, ?, ?, ?, ?, ?) "
                      "ON CONFLICT (member_kind, member_id) DO UPDATE SET image = excluded.image, mime = excluded.mime, "
                      "version = excluded.version, at = excluded.at", (kind, member_id, data, mime, version, util.now()))
    return {"avatar": version}


def _person_only(actor: Actor) -> None:
    if actor.agent_id is not None:
        raise forbidden("Agents do not set avatars; an agent's person sets it.")


def set_mine(pj: Project, actor: Actor, image: Any) -> dict[str, Any]:
    """A person's own avatar in this project; null removes it."""
    _person_only(actor)
    out = _store(pj, "person", actor.person_id, image)
    util.log("avatar_set", project=pj.slug, person=actor.person_id, removed=image is None)
    return out


def set_agent(pj: Project, actor: Actor, name: str, image: Any) -> dict[str, Any]:
    """An agent's avatar, set by its person only; null removes it."""
    _person_only(actor)
    a = pj.db.execute("SELECT id, person_id FROM agents WHERE name = ?", (name,)).fetchone()
    if a is None:
        raise not_found(f"There is no agent '{name}'.")
    if a["person_id"] != actor.person_id:
        raise forbidden("Only an agent's own person sets its avatar.")
    out = _store(pj, "agent", a["id"], image)
    util.log("avatar_set", project=pj.slug, agent=a["id"], by=actor.person_id, removed=image is None)
    return out


def picture(pj: Project, actor: Actor, kind: str, name: str) -> sqlite3.Row:
    """A member's avatar (image, mime, version) for a member with `read`; not_found when it has none."""
    projects.require(pj, actor, "read", "Reading the project needs the read permission.")
    if kind == "person":
        row = pj.db.execute("SELECT person_id AS id FROM people WHERE name = ?", (name,)).fetchone()
    elif kind == "agent":
        row = pj.db.execute("SELECT id FROM agents WHERE name = ?", (name,)).fetchone()
    else:
        row = None
    pic = row and pj.db.execute("SELECT image, mime, version FROM avatars WHERE member_kind = ? AND member_id = ?",
                                (kind, row["id"])).fetchone()
    if not pic:
        raise not_found(f"The {kind} '{name}' has no avatar here.")
    return pic
