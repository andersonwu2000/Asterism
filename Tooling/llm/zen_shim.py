"""OpenCode Zen ⇄ codex CLI translation shim (Responses API), v3.

Measured facts this file answers (2026-08-21/22, free ox-alpha window):
  - Zen's `/responses` STREAM is nonconformant (only output_text.delta,
    no item lifecycle) — codex assembles zero output items. → the shim
    calls Zen NON-stream and synthesizes a conformant SSE sequence.
  - codex hard-injects a `web_search` tool type; Zen 500s on it. → drop.
  - Zen's prefix cache is POISONABLE (a failed generation reproduces on
    the same prefix). → per-request nonce in `instructions`.
  - codex packs every MCP server as ONE `namespace` tool and routes its
    calls only through the ChatGPT-side code-mode convention; ox-alpha
    never learned that convention (it calls flat names), and codex's
    router answers "unsupported call" forever. `code_mode_host = false`
    does NOT flatten (probed). → the shim FLATTENS namespaces for the
    model AND executes the flat `mcp__asterism_tools__*` calls ITSELF,
    in-process, iterating against Zen until the model yields output
    codex can digest. codex never sees a flat call.

Tool execution: `Tooling.knowledge.mcp_tools`'s tools are plain module
functions; the per-spawn context they need travels in env
(`ASTERISM_SPAWN_ATTEMPT_DIR`), which the shim recovers by parsing the
attempts-dir path out of the request text and pins under a global lock
for the duration of each call.

Run:  python -m Tooling.llm.zen_shim [port]   (default 8898)
Key:  OPENCODE_ZEN_API_KEY env, or .env's OPENCODE_ZEN_API_KEY.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

# Upstream: OpenRouter by default (2026-08-22). Zen's gateway kills
# long generations ("Internal server error") and ignores the
# `reasoning.max_tokens` cap that CURES ox-alpha's runaway-reasoning
# pathology (unbounded thinking until max_tokens, content never
# written — measured on both gateways); OpenRouter honors it and also
# serves a conformant /responses. Model ids differ per gateway.
ZEN = os.environ.get("ASTERISM_ZEN_UPSTREAM", "https://openrouter.ai/api/v1")
MODEL_MAP = {"x-preview-f-free": "stealth/ox-alpha"}
ZEN_EFFORT = os.environ.get("ASTERISM_ZEN_EFFORT", "medium")
NS = "mcp__asterism_tools"
LSP_NS = "mcp__lsp"
GATEWAY_MCP = os.environ.get("ASTERISM_GATEWAY_MCP",
                             "http://127.0.0.1:8765/mcp")
MAX_TOOL_ITERATIONS = 80

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

_TOOL_LOCK = threading.Lock()
_ATTEMPT_RE = re.compile(r"[A-Za-z]:\\[^\s'\"]*\.attempts\\[0-9a-fA-F-]{36}")


def _key() -> str:
    names = (("OPENROUTER_API_KEY",) if "openrouter" in ZEN
             else ("OPENCODE_ZEN_API_KEY",))
    for n in names:
        k = os.environ.get(n, "")
        if k:
            return k
    env = os.path.join(_REPO, ".env")
    try:
        for line in open(env, encoding="utf-8"):
            for n in names:
                if line.startswith(n + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    raise SystemExit(f"no {names[0]} (env or .env)")


KEY = None  # filled in main()


def _tools_module():
    from Tooling.knowledge import mcp_tools  # heavy; import once, lazily
    return mcp_tools


def _run_tool(name: str, args: dict, attempt_dir: "str | None") -> str:
    mod = _tools_module()
    fn = getattr(mod, name, None)
    if fn is None:
        return f"unknown tool {name!r}"
    with _TOOL_LOCK:
        prior = os.environ.get("ASTERISM_SPAWN_ATTEMPT_DIR")
        try:
            if attempt_dir:
                os.environ["ASTERISM_SPAWN_ATTEMPT_DIR"] = attempt_dir
            try:
                return str(fn(**args))
            except TypeError as e:
                return f"bad arguments for {name}: {e}"
            except Exception as e:  # noqa: BLE001 — tool result surface
                return f"{name} raised {type(e).__name__}: {e}"
        finally:
            if prior is None:
                os.environ.pop("ASTERISM_SPAWN_ATTEMPT_DIR", None)
            else:
                os.environ["ASTERISM_SPAWN_ATTEMPT_DIR"] = prior


_LSP_SESSIONS: dict = {}


def _mcp_http(payload: dict, headers: dict) -> "tuple[dict | None, dict]":
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        GATEWAY_MCP, data=data,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 **headers})
    with urllib.request.urlopen(req, timeout=1200) as r:
        resp_headers = dict(r.headers)
        raw = r.read().decode("utf-8", "replace")
    if "event-stream" in str(resp_headers.get("Content-Type", "")):
        obj = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:])
                except ValueError:
                    pass
        return obj, resp_headers
    try:
        return json.loads(raw) if raw.strip() else None, resp_headers
    except ValueError:
        return None, resp_headers


def _lsp_session_for(attempt_dir: str) -> "tuple[str, str] | None":
    """(mcp_session_id, gateway_token) for this spawn, cached. The
    gateway's streamable-HTTP MCP wants an initialize handshake; the
    spawn's auth token sits in `<attempt_dir>/_gateway_session.token`
    (written by pipeline._write_mcp_config)."""
    cached = _LSP_SESSIONS.get(attempt_dir)
    if cached:
        return cached
    try:
        token = open(os.path.join(attempt_dir, "_gateway_session.token"),
                     encoding="utf-8").read().strip()
    except OSError:
        return None
    hdr = {"X-Asterism-Session": token}
    obj, rh = _mcp_http({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2025-03-26",
                                    "capabilities": {},
                                    "clientInfo": {"name": "zen-shim",
                                                   "version": "5.0"}}},
                        hdr)
    sid = rh.get("mcp-session-id") or rh.get("Mcp-Session-Id") or ""
    if sid:
        hdr2 = {**hdr, "Mcp-Session-Id": sid}
        try:
            _mcp_http({"jsonrpc": "2.0",
                       "method": "notifications/initialized"}, hdr2)
        except Exception:  # noqa: BLE001 — some servers 202 this oddly
            pass
    _LSP_SESSIONS[attempt_dir] = (sid, token)
    return _LSP_SESSIONS[attempt_dir]


def _run_lsp_tool(name: str, args: dict, attempt_dir: "str | None") -> str:
    if not attempt_dir:
        return "lsp tools need a session; no attempts dir found in request"
    sess = _lsp_session_for(attempt_dir)
    if sess is None:
        return "no _gateway_session.token in attempts dir — lsp unavailable"
    sid, token = sess
    hdr = {"X-Asterism-Session": token}
    if sid:
        hdr["Mcp-Session-Id"] = sid
    try:
        obj, _ = _mcp_http({"jsonrpc": "2.0", "id": 2,
                            "method": "tools/call",
                            "params": {"name": name, "arguments": args}},
                           hdr)
    except urllib.error.HTTPError as e:
        return f"lsp gateway HTTP {e.code}: {e.read()[:200]!r}"
    except Exception as e:  # noqa: BLE001 — tool result surface
        return f"lsp transport error: {e}"
    if not obj:
        return "lsp gateway returned no parseable response"
    if obj.get("error"):
        return f"lsp error: {obj['error']}"
    result = obj.get("result") or {}
    parts = result.get("content") or []
    text = "".join(p.get("text", "") for p in parts
                   if isinstance(p, dict))
    return text or json.dumps(result)[:2000]


def _attempt_dir_of(body: dict) -> "str | None":
    # Scan the WHOLE request: the 20K slice used here first let the
    # skills preamble push the environment context (which carries the
    # attempts dir) past the window — attempt_dir=None, every
    # write_file refused, agent_no_output (measured 2026-08-22).
    hay = json.dumps(body.get("instructions", "")) + json.dumps(
        body.get("input", ""))
    m = _ATTEMPT_RE.search(hay.replace("\\\\", "\\"))
    return m.group(0) if m else None


def _zen_call(body: dict) -> dict:
    """POST once, retrying 5xx/transport errors in place: the free
    endpoint 503s routinely, and aborting the whole request makes codex
    restart the entire turn — a multi-step tool loop then never
    finishes (measured 2026-08-22)."""
    data = json.dumps(body, ensure_ascii=False).encode()
    last: Exception | None = None
    for attempt in range(4):
        req = urllib.request.Request(
            ZEN + "/responses", data=data,
            headers={"Authorization": "Bearer " + KEY,
                     "Content-Type": "application/json",
                     "User-Agent": "asterism-zen-shim/3.0"})
        try:
            with urllib.request.urlopen(req, timeout=1740) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 3:
                raise
            e.read()
            last = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == 3:
                raise
            last = e
        wait = 5 * (attempt + 1)
        print(f"[shim]   retry {attempt+1}/3 in {wait}s ({last})",
              flush=True)
        time.sleep(wait)
    raise RuntimeError("unreachable")


class Shim(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _sse(self, event: str, data: dict) -> None:
        blob = (f"event: {event}\n"
                f"data: {json.dumps(data, ensure_ascii=False)}\n\n").encode()
        self.wfile.write(b"%x\r\n" % len(blob) + blob + b"\r\n")

    def do_POST(self):  # noqa: N802  (stdlib naming)
        n = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(n))
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return
        # --- request surgery -----------------------------------------
        if isinstance(body.get("tools"), list):
            flat = []
            for t in body["tools"]:
                ttype = t.get("type")
                if ttype == "namespace":
                    ns = t.get("name") or "ns"
                    for sub in t.get("tools") or []:
                        f = dict(sub)
                        f["name"] = f"{ns}__{sub.get('name')}"
                        flat.append(f)
                elif ttype == "function":
                    flat.append(t)
                # anything else (web_search etc.) dropped: Zen 1210s
            body["tools"] = flat
        body.pop("client_metadata", None)
        body.pop("stream", None)
        nonce = uuid.uuid4().hex[:12]
        inst = body.get("instructions") or ""
        body["instructions"] = f"[session {nonce}]\n{inst}"
        body["model"] = MODEL_MAP.get(body.get("model"), body.get("model"))
        # Pin the reasoning phase: unbounded (or effort-high), ox-alpha
        # thinks its whole budget away on long-form outputs and never
        # writes content. OpenRouter's /responses rejects
        # `reasoning.max_tokens` but honors `effort`, and low/medium
        # both cure the runaway (measured 2026-08-22: 1000-word essay
        # delivered at both; unbounded = 8000 tokens of reasoning and
        # zero content).
        body["reasoning"] = {"effort": ZEN_EFFORT}
        attempt_dir = _attempt_dir_of(body)
        if not isinstance(body.get("input"), list):
            body["input"] = [body.get("input")] if body.get("input") else []

        # --- Zen loop: absorb flat-MCP calls in the shim -------------
        t0 = time.time()
        iters = 0
        tool_calls_run = 0
        resp: dict = {}
        try:
            while True:
                t_call = time.time()
                resp = _zen_call(body)
                items = resp.get("output") or []
                if not items:
                    # Degenerate empty response (no output array at
                    # all) — the runaway/overload face that survives
                    # even the effort pin, intermittently. Same cure
                    # as 5xx: retry in place with a fresh nonce so the
                    # poisonable prefix cannot replay it.
                    for extra in range(2):
                        body["instructions"] = (
                            f"[session {uuid.uuid4().hex[:12]}]" + chr(10) + inst)
                        print(f"[shim]   empty response — retry "
                              f"{extra+1}/2", flush=True)
                        resp = _zen_call(body)
                        items = resp.get("output") or []
                        if items:
                            break
                mine = [it for it in items
                        if it.get("type") == "function_call"
                        and (str(it.get("name", "")).startswith(NS + "__")
                             or str(it.get("name", "")).startswith(
                                 LSP_NS + "__"))]
                print(f"[shim] iter {iters}: zen {time.time()-t_call:.0f}s, "
                      f"{len(items)} item(s), "
                      + (", ".join(str(it.get('name'))[len(NS)+2:]
                                   for it in mine) or "final"),
                      flush=True)
                if not mine or iters >= MAX_TOOL_ITERATIONS:
                    break
                iters += 1
                for it in items:
                    body["input"].append(it)
                    if it not in mine:
                        continue
                    full = str(it.get("name"))
                    try:
                        args = json.loads(it.get("arguments") or "{}")
                    except ValueError:
                        args = {}
                    t_tool = time.time()
                    if full.startswith(LSP_NS + "__"):
                        tool = full[len(LSP_NS) + 2:]
                        out = _run_lsp_tool(tool, args, attempt_dir)
                    else:
                        tool = full[len(NS) + 2:]
                        out = _run_tool(tool, args, attempt_dir)
                    print(f"[shim]   tool {tool} {time.time()-t_tool:.1f}s "
                          f"-> {len(out)}B", flush=True)
                    tool_calls_run += 1
                    body["input"].append({
                        "type": "function_call_output",
                        "call_id": it.get("call_id") or it.get("id"),
                        "output": out})
        except urllib.error.HTTPError as e:
            payload = e.read()
            print(f"[shim] upstream {e.code} after {time.time()-t0:.0f}s "
                  f"(iters={iters}): {payload[:160]!r}", flush=True)
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        except Exception as e:  # noqa: BLE001 — network layer
            print(f"[shim] transport error (iters={iters}): {e}", flush=True)
            self.send_response(502)
            self.end_headers()
            return

        # --- synthesize a conformant Responses SSE stream ------------
        items = [it for it in (resp.get("output") or [])
                 if not (it.get("type") == "function_call"
                         and (str(it.get("name", "")).startswith(NS + "__")
                              or str(it.get("name", "")).startswith(
                                  LSP_NS + "__")))]
        usage = resp.get("usage") or {}
        print(f"[shim] ok {time.time()-t0:.0f}s iters={iters} "
              f"tools={tool_calls_run} items={len(items)} "
              f"usage={usage.get('output_tokens')}out", flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        seq = 0

        def ev(event: str, extra: dict) -> None:
            nonlocal seq
            seq += 1
            self._sse(event, {"type": event, "sequence_number": seq, **extra})

        shell = {k: v for k, v in resp.items() if k != "output"}
        shell["output"] = []
        ev("response.created", {"response": shell})
        ev("response.in_progress", {"response": shell})
        for idx, item in enumerate(items):
            ev("response.output_item.added",
               {"output_index": idx, "item": {**item,
                **({"content": []} if item.get("type") == "message" else {})}})
            if item.get("type") == "message":
                for ci, part in enumerate(item.get("content") or []):
                    ev("response.content_part.added",
                       {"item_id": item.get("id"), "output_index": idx,
                        "content_index": ci, "part": {**part, "text": ""}})
                    text = part.get("text") or ""
                    if text:
                        ev("response.output_text.delta",
                           {"item_id": item.get("id"), "output_index": idx,
                            "content_index": ci, "delta": text,
                            "logprobs": []})
                    ev("response.output_text.done",
                       {"item_id": item.get("id"), "output_index": idx,
                        "content_index": ci, "text": text, "logprobs": []})
                    ev("response.content_part.done",
                       {"item_id": item.get("id"), "output_index": idx,
                        "content_index": ci, "part": part})
            elif item.get("type") == "function_call":
                args = item.get("arguments") or ""
                if args:
                    ev("response.function_call_arguments.delta",
                       {"item_id": item.get("id"), "output_index": idx,
                        "delta": args})
                ev("response.function_call_arguments.done",
                   {"item_id": item.get("id"), "output_index": idx,
                    "arguments": args})
            ev("response.output_item.done",
               {"output_index": idx, "item": item})
        done = dict(resp)
        done["status"] = "completed"
        done["output"] = items
        ev("response.completed", {"response": done})
        self.wfile.write(b"0\r\n\r\n")

    def log_message(self, *a):  # noqa: D102 — quiet
        pass


def main() -> int:
    global KEY
    KEY = _key()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8898
    print(f"[shim] zen shim v3 on 127.0.0.1:{port} -> {ZEN}", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Shim).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
