#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Daimon Legal
"""Tiny stdio MCP server that exposes the calling framework's tools to the CLI.

The CLI sees the framework's OpenAI `tools` as MCP tools. The parent bridge
stops the CLI the instant it emits a real tool call, so the framework, not this
process, actually runs the tool. This server therefore never executes anything;
its only jobs are to advertise the tool list and to refuse execution loudly if
the CLI ever tries to run one itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _read_tools(path: str) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text())
    except Exception:
        return []
    out: list[dict] = []
    for t in data or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") if t.get("type") == "function" else t
        if not isinstance(fn, dict) or not fn.get("name"):
            continue
        out.append({
            "name": str(fn.get("name")),
            "description": str(fn.get("description") or ""),
            "inputSchema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return out


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("mcp_bridge: missing tools manifest path\n")
        sys.exit(2)
    tools = _read_tools(sys.argv[1])

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        msg_id = msg.get("id")

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cli-bridge-tools", "version": "1.0.0"},
                },
            })
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}})
        elif method == "tools/call":
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": "ERROR: tool execution is delegated to the calling framework. "
                                "Stop after emitting the tool call and let the framework execute it.",
                    }],
                    "isError": True,
                },
            })
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
        elif msg_id is not None:
            _send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"method not found: {method}"}})


if __name__ == "__main__":
    try:
        main()
    except (BrokenPipeError, KeyboardInterrupt):
        pass
