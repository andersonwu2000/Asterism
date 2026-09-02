"""serve.lean_eval — the reader's Lean scratch pipeline.

One staged-elaborate endpoint, two surfaces (charter: the New page's
authoring check and the Library chapter's probe blocks). The browser
sends ordered code parts; we stage ONE throwaway .lean under
`.asterism/eval/`, run it through the warm gateway, and map the
diagnostics back to per-part local line numbers. `#check` / `#print
axioms` output arrives as severity-'information' diagnostics — the
frontend renders those as results, not errors.

Display-side only, by construction: `write_olean=False`, the staged
file is unlinked in `finally`, and nothing here touches proofs/ or the
DB — the same throwaway standing as the Gate B probe. `#eval` can run
arbitrary IO, which on this localhost solo surface is the same trust
level as the engine compiling agent code all day.

Gateway coupling is soft: if the gateway is not ready we kick ONE
background warm-up thread and return {"status": "warming"} immediately
— the frontend retries. Imports of modules THIS workspace builds
(`Library.*`, `Problems.*`) get an incremental `lake build` first (the
gateway imports on-disk oleans as-is and does NOT rebuild stale deps;
the librarian rewrites Library files and the engine writes Problems
ones, so a chapter probe or a Project document can otherwise race a
run's mid-chain state).
"""
from __future__ import annotations

import re
import tempfile
import threading
import time
from pathlib import Path

import asyncio

import anyio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

_MAX_CODE = 200_000  # chars, all parts combined — scratch, not upload
_IMPORT_LINE = re.compile(r"^\s*(?:public\s+|private\s+)?import\s+", re.M)

_warm_lock = threading.Lock()
_warm_started = False


class EvalPart(BaseModel):
    id: str
    code: str


class EvalBody(BaseModel):
    parts: list[EvalPart]
    imports: list[str] | None = None


_IMPORT_CAPTURE = re.compile(
    r"^\s*(?:public\s+|private\s+)?import\s+([\w.]+)\s*$", re.M)

#: The module trees THIS workspace builds. The gateway imports on-disk
#: oleans as-is and never rebuilds a stale dependency, so an import of
#: one of these has to be made fresh before the elaboration reads it:
#: `Library.*` because the librarian rewrites those files under a
#: running probe, `Problems.*` because a Project document imports the
#: engine's own proofs while the engine is still writing them (HID
#: §1.2-2). Mathlib and the toolchain are not ours to rebuild.
_LOCAL_PREFIXES = ("Library.", "Problems.")


def _local_imports(text: str) -> "list[str]":
    """Workspace-built modules the assembled file imports, in order, and
    each one once.

    Read off the assembled TEXT rather than the request's `imports`
    list, because the list is not where every import comes from: the
    first part may open with its own header — which is exactly how a
    `.lean` document on the Project's shelf names the proofs it cites —
    and a module named there is precisely as stale as one named in the
    list. Later parts' imports are already blanked by `_assemble` (their
    content is inlined above), so they cannot reach this scan."""
    out: "list[str]" = []
    for m in _IMPORT_CAPTURE.finditer(text):
        name = m.group(1)
        if name.startswith(_LOCAL_PREFIXES) and name not in out:
            out.append(name)
    return out


def _assemble(parts: "list[tuple[str, str]]",
              imports: "list[str]") -> "tuple[str, int, list[tuple[str, int, int]]]":
    """Concatenate parts after an import preamble.

    Returns (text, preamble_lines, spans) where spans is
    [(part_id, first_global_line, last_global_line)] (1-indexed,
    inclusive). Import handling mirrors how the parts land on disk as
    ONE file: the first part may open with its own header; later parts'
    import lines are BLANKED in place (line counts must not shift — the
    New page's Root imports `Problems.<name>.Defs`, whose content is
    the part right above) and any non-`Problems.*` module they name is
    hoisted into the preamble. When nothing supplies an import,
    `import Mathlib` is prepended."""
    seen: "set[str]" = set(imports)
    for m in _IMPORT_CAPTURE.finditer(parts[0][1]) if parts else ():
        seen.add(m.group(1))
    hoisted: "list[str]" = []
    cleaned: "list[tuple[str, list[str]]]" = []
    for i, (pid, code) in enumerate(parts):
        body = code.splitlines() or [""]
        if i > 0:
            for j, ln in enumerate(body):
                im = _IMPORT_CAPTURE.match(ln)
                if im:
                    name = im.group(1)
                    if not name.startswith("Problems.") and name not in seen:
                        hoisted.append(name)
                        seen.add(name)
                    body[j] = ""  # keep the line, drop the mid-file import
        cleaned.append((pid, body))
    preamble = [f"import {m}" for m in list(imports) + hoisted]
    if not preamble and not (parts and _IMPORT_LINE.match(parts[0][1])):
        preamble = ["import Mathlib"]
    lines: "list[str]" = list(preamble)
    spans: "list[tuple[str, int, int]]" = []
    for pid, body in cleaned:
        start = len(lines) + 1
        lines.extend(body)
        spans.append((pid, start, len(lines)))
    return "\n".join(lines) + "\n", len(preamble), spans


def _global_cursor(cursor: "dict | None",
                   spans: "list[tuple[str, int, int]]",
                   ) -> "tuple[int, int] | None":
    """{part, line, col} in a part's local frame → (global_line, col)
    in the assembled file. None when the cursor doesn't resolve."""
    if not cursor or not spans:
        return None
    for pid, start, end in spans:
        if pid == cursor.get("part"):
            line = cursor.get("line")
            if not isinstance(line, int) or line < 1:
                return None
            return min(start + line - 1, end), int(cursor.get("col") or 0)
    return None


def _map_diags(diags: "list[dict]", preamble_lines: int,
               spans: "list[tuple[str, int, int]]") -> "dict[str, list[dict]]":
    """Global diagnostic lines → {part_id: [diag with part-local line]}.
    Preamble hits (bad import) land under '_preamble'."""
    out: "dict[str, list[dict]]" = {}
    for d in diags:
        line = d.get("line")
        entry = {"line": None, "col": d.get("col"),
                 "severity": str(d.get("severity") or "error"),
                 "message": str(d.get("message") or "")}
        target = "_preamble"
        if isinstance(line, int) and line > preamble_lines:
            for pid, start, end in spans:
                if start <= line <= end:
                    target = pid
                    entry["line"] = line - start + 1
                    break
            else:
                target = spans[-1][0] if spans else "_preamble"
                if spans:
                    entry["line"] = max(1, line - spans[-1][1] + 1)
        out.setdefault(target, []).append(entry)
    return out


def register(app: FastAPI, workspace: Path) -> None:

    def _ensure_gateway(force: bool = False) -> "str | None":
        """'ready' → proceed; otherwise kick ONE warm-up thread and
        report the phase for the frontend's retry loop. `force=True`
        kicks even on a healthy gateway — start_gateway's fingerprint
        gate then kills a stale-code one and relaunches (the serve path
        that discovers staleness: /interactive 404s on an old build)."""
        from ..lsp import lifecycle as gw
        phase = gw.gateway_phase(workspace)
        if phase == "ready" and not force:
            return None
        global _warm_started
        with _warm_lock:
            if not _warm_started:
                _warm_started = True

                def _warm() -> None:
                    global _warm_started
                    try:
                        gw.start_gateway(workspace)
                    except Exception:  # noqa: BLE001 — retried on next eval
                        pass
                    finally:
                        _warm_started = False

                threading.Thread(target=_warm, name="serve-gateway-warm",
                                 daemon=True).start()
        return phase or "starting"

    @app.post("/api/lean/eval")
    def lean_eval(body: EvalBody) -> dict:
        """Stage the parts, elaborate on the warm gateway, return
        per-part diagnostics. {"status": "warming"} means retry."""
        parts = [(p.id, p.code) for p in body.parts if p.code.strip()]
        if not parts:
            raise HTTPException(status_code=400, detail="no code")
        if sum(len(c) for _, c in parts) > _MAX_CODE:
            raise HTTPException(status_code=413, detail="code too large")
        imports = list(body.imports or [])

        phase = _ensure_gateway()
        if phase is not None:
            return {"status": "warming", "phase": phase}

        text, n_pre, spans = _assemble(parts, imports)

        # Chapter probes import Library modules and Project documents
        # import Problems ones; rebuild them incrementally first (no-op
        # seconds when fresh) so the elaboration sees the text on disk,
        # not a stale olean.
        local_mods = _local_imports(text)
        if local_mods:
            from ..pipeline import _lake
            ok, detail = _lake.lake_build_modules(workspace, local_mods)
            if not ok:
                return {"status": "ok", "ok": False, "wall_sec": 0.0,
                        "parts": {}, "preamble": [{
                            "line": None, "col": None, "severity": "error",
                            "message": "module rebuild failed: "
                                       + (detail or "")[:800]}]}

        evdir = workspace / ".asterism" / "eval"
        evdir.mkdir(parents=True, exist_ok=True)
        from ..lsp import lifecycle as gw
        t0 = time.monotonic()
        fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="probe_",
                                   dir=str(evdir))
        tmp_path = Path(tmp)
        try:
            import os
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            v = gw.verify_file(tmp_path, write_olean=False,
                               workspace=workspace, _retry_delays=())
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        if v.get("error"):
            code = 503 if v.get("transient") else 500
            raise HTTPException(status_code=code,
                                detail=f"EVAL_INFRA: {v['error']}")
        mapped = _map_diags(list(v.get("diagnostics") or []), n_pre, spans)
        return {
            "status": "ok",
            "ok": bool(v.get("ok")),
            "wall_sec": round(time.monotonic() - t0, 2),
            "parts": {pid: mapped.get(pid, []) for pid, _, _ in spans},
            "preamble": mapped.get("_preamble", []),
        }

    @app.websocket("/api/lean/session")
    async def lean_session(ws: WebSocket) -> None:
        """The browser InfoView: one interactive gateway session per
        connection (the RESERVED slot — pipelines and the editor never
        touch each other's slots). Messages in: {type: "sync", parts,
        imports?, cursor?, seq} for buffer changes, {type: "cursor",
        cursor, seq} for caret moves. Out: state / goal / warming /
        busy / error, each echoing seq so the client drops stale
        responses. Disconnect releases the slot."""
        from ..lsp import lifecycle as gw
        await ws.accept()
        token: "str | None" = None
        spans: "list[tuple[str, int, int]]" = []
        n_pre = 0
        built: "set[str]" = set()  # Library modules lake-built this connection
        try:
            while True:
                msg = await ws.receive_json()
                seq = msg.get("seq")
                kind = msg.get("type")
                if kind == "sync":
                    parts = [(str(p.get("id")), str(p.get("code") or ""))
                             for p in (msg.get("parts") or [])
                             if str(p.get("code") or "").strip()]
                    if not parts:
                        await ws.send_json({"type": "state", "seq": seq,
                                            "parts": {}, "preamble": [],
                                            "goal": None, "note": None})
                        continue
                    phase = _ensure_gateway()
                    if phase is not None:
                        await ws.send_json({"type": "warming", "seq": seq,
                                            "phase": phase})
                        continue
                    imports = list(msg.get("imports") or [])
                    text, n_pre, spans = _assemble(parts, imports)
                    # chapter probes import Library modules, Project
                    # documents import Problems ones — same incremental
                    # freshness build the one-shot path does (the gateway
                    # imports on-disk oleans as-is), once per module per
                    # connection
                    local_mods = [m for m in _local_imports(text)
                                  if m not in built]
                    if local_mods:
                        from ..pipeline import _lake
                        ok, detail = await asyncio.to_thread(
                            _lake.lake_build_modules, workspace, local_mods)
                        if not ok:
                            await ws.send_json({
                                "type": "error", "seq": seq,
                                "detail": "module rebuild failed: "
                                          + (detail or "")[:400]})
                            continue
                        built.update(local_mods)
                    cur = _global_cursor(msg.get("cursor"), spans)
                    r: dict = {}
                    for _attempt in (1, 2):
                        if token is None:
                            reg = await asyncio.to_thread(
                                gw.interactive_register, text)
                            if reg.get("http_status") == 404:
                                # healthy but STALE gateway (no
                                # /interactive on the old build) —
                                # force the fingerprint relaunch and
                                # let the client's warming retry land
                                # on the fresh one
                                _ensure_gateway(force=True)
                                await ws.send_json({
                                    "type": "warming", "seq": seq,
                                    "phase": "restarting"})
                                r = {}
                                break
                            if reg.get("error"):
                                busy = reg.get("http_status") == 409
                                await ws.send_json({
                                    "type": "busy" if busy else "error",
                                    "seq": seq,
                                    "detail": str(reg["error"])})
                                r = {}
                                break
                            token = str(reg["session_token"])
                        r = await asyncio.to_thread(
                            gw.interactive_sync, token, text,
                            cur[0] if cur else None,
                            cur[1] if cur else 0)
                        if r.get("error"):
                            # swept claim / gateway restart — one clean
                            # re-register before surfacing the error
                            token = None
                            continue
                        break
                    if not r:
                        continue
                    if r.get("error"):
                        await ws.send_json({"type": "error", "seq": seq,
                                            "detail": str(r["error"])})
                        continue
                    mapped = _map_diags(list(r.get("diagnostics") or []),
                                        n_pre, spans)
                    await ws.send_json({
                        "type": "state", "seq": seq,
                        "parts": {pid: mapped.get(pid, [])
                                  for pid, _, _ in spans},
                        "preamble": mapped.get("_preamble", []),
                        "goal": r.get("goal"), "note": r.get("note")})
                elif kind == "cursor" and token is not None:
                    cur = _global_cursor(msg.get("cursor"), spans)
                    if cur is None:
                        continue
                    r = await asyncio.to_thread(
                        gw.interactive_goal, token, cur[0], cur[1])
                    if r.get("error"):
                        continue  # cursor peeks are best-effort
                    await ws.send_json({"type": "goal", "seq": seq,
                                        "goal": r.get("goal"),
                                        "note": r.get("note")})
        except WebSocketDisconnect:
            pass
        finally:
            if token is not None:
                # Task teardown (TestClient exit, server shutdown) can
                # cancel this handler right after the disconnect lands;
                # an unshielded await here is a cancellation checkpoint
                # and the release silently dies with it, leaking the
                # reserved slot. Shield so the slot always comes back.
                with anyio.CancelScope(shield=True):
                    await asyncio.to_thread(gw.interactive_release, token)
