"""Reads that only move when they changed.

The console polls; most polls answer with the bytes the last one already
has. The Sky's `/api/problems/{p}` is ~800KB on a 500-goal task and the
Timeline feeds are not far behind, so a conditional GET is worth more
here than any amount of shaving on the aggregation itself.

The tag is `sha1` of the serialized body — a statement about the bytes
and nothing else. A version key assembled from columns somebody
remembered would be the usual way, and the usual way is how a screen
freezes: these payloads fold in live worker leases, on-disk signatures
and the daemon's own state, and the first field the key forgot would
stop reaching the reader with no error anywhere. Hashing the body cannot
be wrong about the body.

The aggregation still runs on a 304: it is the cheap half (measured
71ms against 798KB on the wire), and a reader must never be told
"unchanged" about a reading nobody took.
"""
from __future__ import annotations

import hashlib
import json

from fastapi import Request
from fastapi.responses import Response


def conditional_json(request: Request, payload: dict) -> Response:
    """A JSON response carrying its own ETag; 304 when the caller
    already holds these exact bytes."""
    body = json.dumps(payload, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    tag = 'W/"%s"' % hashlib.sha1(body).hexdigest()
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers={"ETag": tag})
    return Response(content=body, media_type="application/json",
                    headers={"ETag": tag})
