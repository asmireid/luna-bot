from __future__ import annotations

import asyncio
import json

from .base import MCPTransport


class MCPStdioTransport(MCPTransport):
    def __init__(self, command: list[str], env: dict | None = None, cwd: str | None = None) -> None:
        self.command = command
        self.env = env
        self.cwd = cwd
        self.process: asyncio.subprocess.Process | None = None
        self._request_id = 0

    async def open(self) -> None:
        if self.process is not None:
            return

        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
            cwd=self.cwd,
        )

    async def close(self) -> None:
        if self.process is None:
            return

        if self.process.stdin:
            self.process.stdin.close()
        self.process.terminate()
        await self.process.wait()
        self.process = None

    async def request(self, method: str, params: dict | None = None):
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        response = await self._send_and_read(payload)
        if "error" in response:
            raise RuntimeError(f"MCP request failed: {response['error']}")
        return response.get("result", {})

    async def notify(self, method: str, params: dict | None = None) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        await self._write_message(payload)

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_and_read(self, payload: dict):
        await self._write_message(payload)
        return await self._read_message()

    async def _write_message(self, payload: dict) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("MCP stdio transport is not open.")
        self.process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def _read_message(self) -> dict:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("MCP stdio transport is not open.")

        while True:
            line = await self.process.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed the stdio stream.")
            text = line.decode("utf-8").strip()
            if text:
                return json.loads(text)
