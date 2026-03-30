"""Minimal JSON-RPC 2.0 server over stdin/stdout."""

import asyncio
import json
import sys
from typing import Any, Callable


class JsonRpcServer:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}

    def method(self, name: str) -> Callable:
        """Decorator to register an async handler for a JSON-RPC method."""
        def decorator(fn: Callable) -> Callable:
            self._handlers[name] = fn
            return fn
        return decorator

    def _make_error(self, id: Any, code: int, message: str) -> str:
        response = {
            "jsonrpc": "2.0",
            "id": id,
            "error": {"code": code, "message": message},
        }
        return json.dumps(response)

    def _make_result(self, id: Any, result: Any) -> str:
        response = {
            "jsonrpc": "2.0",
            "id": id,
            "result": result,
        }
        return json.dumps(response)

    async def _dispatch(self, line: str) -> str | None:
        """Parse one JSON-RPC request line and return the response string."""
        req_id = None
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            return self._make_error(None, -32700, f"Parse error: {exc}")

        req_id = req.get("id")
        method_name = req.get("method")

        if method_name not in self._handlers:
            return self._make_error(req_id, -32601, f"Method not found: {method_name}")

        handler = self._handlers[method_name]
        params = req.get("params", {})

        try:
            if isinstance(params, list):
                result = await handler(*params)
            elif isinstance(params, dict):
                result = await handler(**params)
            else:
                result = await handler()
        except Exception as exc:
            return self._make_error(req_id, -32603, f"Internal error: {exc}")

        # Notifications (no id) get no response
        if req_id is None:
            return None

        return self._make_result(req_id, result)

    async def run(self) -> None:
        """Read JSON-RPC requests from stdin, write responses to stdout."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line_bytes = await reader.readline()
            except Exception:
                break

            if not line_bytes:
                # EOF
                break

            line = line_bytes.decode("utf-8").rstrip("\n")
            if not line.strip():
                continue

            response = await self._dispatch(line)
            if response is not None:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
